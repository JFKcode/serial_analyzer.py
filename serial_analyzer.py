# wykorzystujemy bibliotękę PyQt5 i dodatkowo pyqtgraph
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from PyQt5 import QtWidgets
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
import time
import pyqtgraph as pgraph
import sys

class CustomPlotWidget(pgraph.GraphicsWindow):
    plotItem_temp = None
    plotItem_both = None
    
    plotDataItem_temp = None
    plotDataItem_both_temp = None
    plotDataItem_both_RPM = None
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.plotItem_temp = self.addPlot(title="Temperature")
        self.plotItem_both = self.addPlot(title="Temp and RPM(/100)")

        self.plotDataItem_temp = self.plotItem_temp.plot([], pen ='g')
        self.plotDataItem_both_temp = self.plotItem_both.plot([], pen ='g')
        self.plotDataItem_both_RPM = self.plotItem_both.plot([], pen ='r')
        

    def setData(self, x, y, z):
        self.plotDataItem_temp.setData(x, y)
        self.plotDataItem_both_temp.setData(x, y)
        self.plotDataItem_both_RPM.setData(x, [singleZ / 100 for singleZ in z])

class Ui(QtWidgets.QMainWindow):
    port : QSerialPort = None
    tempLabel : QLabel = None
    rpmLabel : QLabel = None
    tempEnableLabel : QLabel = None
    dataContainer : QWidget = None
    connectionContainer : QWidget = None
    portsSelector : QComboBox = None
    aquiredData : str = ""

    graphWidget : pgraph.PlotWidget = None

    temperatureData = []
    rpmData = []
    timeData = []
    startTime = 0
    tempLine = None

    logFileName = "log.csv" # ścieżka pliku logowania

    plotItemsCount = 50 # ilość punktów do wyświetlenia na wykresie

    temperature : float = 0.0 # temperatura otrzymana po serialporcie
    rpm : int = 0 # rpm otrzymane po serial porcie
    tempEnable : int = -10000 #średnia temperatura załączania
    
    def __init__(self): # konstruktor
        super(Ui, self).__init__() # konstruktor klasy bazowej
        self.setCentralWidget(QWidget())
        self.centralWidget().setLayout(QVBoxLayout()) # główny widget całej apki, ustawiamy layout
        self.connectionContainer = QWidget() # tworzymy kontener na ustawienia połączenia
        self.connectionContainer.setLayout(QVBoxLayout()) #nadajemy mu wertykalny layout
        self.portsSelector = QComboBox() # tworzymy combo box do połączenia

        for port in QSerialPortInfo.availablePorts(): # skanujemy dostępne porty
            self.portsSelector.addItem(port.portName(), port) # do combo boxa dodajemy nazwę portu i obiekt
        if(self.portsSelector.count()>0): 
            connectBtn = QPushButton("Connect")
            # łączymy slot clicked z funkcją/slotem onPortSelection
            connectBtn.clicked.connect(self.onPortSelection)
            self.connectionContainer.layout().addWidget(self.portsSelector)
            self.connectionContainer.layout().addWidget(connectBtn)
        else:
            self.connectionContainer.layout().addWidget(QLabel("No ports available."))
            self.connectionContainer.layout().addWidget(QLabel("Connect the device and restart this application."))

        self.centralWidget().layout().addWidget(self.connectionContainer) # dodajemy connectioncontainer do centralwidget (by był wyświetlony)
        #tworzymy labelki pod zmienne
        self.tempLabel = QLabel(str(self.temperature)) 
        self.rpmLabel = QLabel(str(self.rpm))  
        self.tempEnableLabel = QLabel("0")

        self.dataContainer = QWidget()
        self.dataContainer.setLayout(QHBoxLayout())

        tempContainer = QWidget()
        tempContainer.setLayout(QHBoxLayout())
        tempContainer.layout().addWidget(QLabel("Temperature: "))
        tempContainer.layout().addWidget(self.tempLabel)
        self.dataContainer.layout().addWidget(tempContainer)

        rpmContainer = QWidget()
        rpmContainer.setLayout(QHBoxLayout())
        rpmContainer.layout().addWidget(QLabel("RPM: "))
        rpmContainer.layout().addWidget(self.rpmLabel)
        self.dataContainer.layout().addWidget(rpmContainer)

        tempEnableContainer = QWidget()
        tempEnableContainer.setLayout(QHBoxLayout())
        tempEnableContainer.layout().addWidget(QLabel("AVG temp enable: "))
        tempEnableContainer.layout().addWidget(self.tempEnableLabel)
        self.dataContainer.layout().addWidget(tempEnableContainer)

        self.centralWidget().layout().addWidget(self.dataContainer)
        self.dataContainer.hide()
        self.graphWidget = CustomPlotWidget()
        self.graphWidget.setBackground('w')
        self.centralWidget().layout().addWidget(self.graphWidget)
        self.show()
    
    def connect(self) -> bool:
        self.port = QSerialPort(self)
        self.port.setBaudRate(9600)
        # pobieram z comboboxa port do połączenia
        self.port.setPort(self.portsSelector.currentData())
        #print(self.portsSelector.currentData().portName())
        self.port.setDataBits(QSerialPort.Data8)
        self.port.setStopBits(QSerialPort.OneStop)
        self.port.setParity(QSerialPort.NoParity)
        self.port.setFlowControl(QSerialPort.NoFlowControl)
        # łączenie sygnału z QSerialPort, który jest emitowany w momencie przyjścia nowych danych
        self.port.readyRead.connect(self.dataReady)
        if(self.port.open(QSerialPort.ReadOnly)):
            return True
        return False

    @pyqtSlot()
    def dataReady(self):
        # odczytywanie danych z serial portu
        self.aquiredData += str(self.port.readAll())
        # footerem jest '\r\nb\'' (oznacza to że bezpiecznie można przeczytać całą ramkę, albo cała ramka dotarła)
        splitted = self.aquiredData.split('\r\nb\'')

        # self.aquiredData = 11.22,0\r\n1
        # splitted[0] = 11.22,0\r\n splitted[1] = 1

        #sprawdzamy czy przyszła cała ramka
        if(len(splitted)>0):
            toParse = splitted[0]
            # usuwamy z aquiredData aktualnie przetwarzaną ramkę
            self.aquiredData = self.aquiredData[len(toParse)-1:-1]

            #splittedVars[0] - temperatura splittedVars[1] - rpmy
            splittedVars = toParse.split(',')
            # sprawdzamy czy poprawnie sformatowano tekst na dwie zmienne
            if(len(splittedVars)==2):
                try:
                    # zaczynamy liczyć czas (od pierwszej ramki)
                    if(self.startTime == 0): self.startTime = time.time()
                    # aktualny czas odejmujemy czas startu i to zwraca czas w sekundach od pierwszej ramki
                    currentTime = int((time.time()-self.startTime)*1000)
                    # trzeba pamiętać że po splicie otrzymujemy wartości typu (lewa strona) b'12.0  prawa strona 500\r\n' 
                    self.temperature = float(splittedVars[0][2:-1])
                    prevRPM = self.rpm
                    self.rpm = int(splittedVars[1][0:-5])
                    if(prevRPM < 1000 and self.rpm>1000):
                        
                        if(self.tempEnable==-10000): 
                            self.tempEnable = self.temperature
                        else:
                            self.tempEnable = self.tempEnable * 0.95 + self.temperature * 0.05
                    self.saveData(str(currentTime)+","+str(self.temperature)+","+str(self.rpm)+"\n")

                    # zapisujemy sobie nowe wartości do listy by wykorzystać to do rysowania wykresu
                    self.temperatureData.append(self.temperature)
                    self.rpmData.append(self.rpm)
                    self.timeData.append(currentTime)

                    # swap 
                    if(len(self.temperatureData)>self.plotItemsCount):
                        self.temperatureData.pop(0)
                        self.timeData.pop(0)
                        self.rpmData.pop(0)
                    self.updateView()
                except:
                    pass

    def saveData(self, text):
        file = open(self.logFileName, "a+")
        file.write(text)
        file.close()

    @pyqtSlot()
    def updateView(self):
        self.tempLabel.setText(str(self.temperature))
        self.rpmLabel.setText(str(self.rpm))
        if self.tempEnable!=-10000:
            self.tempEnableLabel.setText(str(self.tempEnable))
        self.graphWidget.setData(self.timeData, self.temperatureData, self.rpmData)

    @pyqtSlot()
    def onPortSelection(self):
        if(self.connect()): 
            print("Connected!")
            self.connectionContainer.hide()
            self.dataContainer.show()

app = QtWidgets.QApplication(sys.argv)
window = Ui()
app.exec_()