APP_NAME = btApp
SOURCE_FILE = BluetoothControl.cpp

bluetoothApp:
	g++ -o ${APP_NAME} ${SOURCE_FILE}

clean:
	rm ./$(APP_NAME)

run:
	./$(APP_NAME)

sanityCheck:
	echo ${APP_NAME}	