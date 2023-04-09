# Restricted Zone Access Detection with Kafka Connection
Deepstream application to detect people inside pre defined restricted zones. In case a person is detected inside these zones the bounding boxes change in color and a metadata message is send to a kafka broker with all the information of the event

## Dependencies

1. Install Kafka dependencies

The Kafka adapter uses librdkafka for the underlying protocol implementation. This library must be installed prior to use. To install librdkakfa, enter these commands:

```
git clone https://github.com/edenhill/librdkafka.git
cd librdkafka
git reset --hard 063a9ae7a65cebdf1cc128da9815c05f91a2a996
./configure
make
sudo make install
sudo cp /usr/local/lib/librdkafka* /opt/nvidia/deepstream/deepstream-5.0/lib
```

Install additional dependencies:
```
sudo apt-get install libglib2.0 libglib2.0-dev
sudo apt-get install libjansson4 libjansson-dev
```

2. Install requirements.txt

```
pip install -r requirements.txt
```

## How to run the application

1. Pull deepstream python bindings docker
```
docker pull serge3006/deepstream-python-bindings-6.1
```

2. Allow external applications to connect to the host's X display:
```
xhost +
```
3. Set env variables
```
export DISPLAY =:1
```
4. Run the docker container
```
docker run --gpus all -it --net=host --privileged -v /tmp/.X11-unix:/tmp/.X11-unix -v <app_folder>/:/app/ -w /app/ -e DISPLAY=$DISPLAY serge3006/deepstream-python-bindings-6.1
```

5. Install requirements
```
pip install -r requirements.txt
```
6. Run the application
```
python3 -m main --config_path configs/app_config.json --protolib_path /opt/nvidia/deepstream/deepstream-6.1/lib/libnvds_kafka_proto.so --connection_string host;port;topic
```