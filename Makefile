APP_NAME = btApp
SOURCE_FILE = BluetoothControl.cpp
LIBS = -lbluetooth

bluetoothApp:
	g++ -o ${APP_NAME} ${SOURCE_FILE} ${LIBS}

clean:
	rm ./$(APP_NAME)

run:
	sudo ./$(APP_NAME)

sanityCheck:
	echo ${APP_NAME}	