# Restricted Zone Access Detection with Kafka Connection
Deepstream application to detect people inside pre defined restricted zones. In case a person is detected inside these zones the bounding boxes change in color and a metadata message is send to a kafka broker with all the information of the event

![alt text](https://github.com/Serge3006/deepstream-kafka/blob/master/resources/output.gif "Application output")


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

## Setup Apache Kafka

The following instructions are based on the official documentation of Apache Kafka taken from here: https://kafka.apache.org/quickstart, for more details or other ways to start the service checkout the official website.

1. Download the latest kafka and extract it

```
tar -xzf kafka_2.13-3.4.0.tgz
cd kafka_2.13-3.4.0
```

2. Start the ZooKeper server in one terminal
```
bin/zookeeper-server-start.sh config/zookeeper.properties
```

3. Start the Kafka server in another terminal
```
bin/kafka-server-start.sh config/server.properties
```

4. Create a topic in another terminal
```
bin/kafka-topics.sh --create --topic deepstream-topic --bootstrap-server localhost:9092
```

5. In the same terminal run the console consumer client to read the events

```
bin/kafka-console-consumer.sh --topic deepstream-topic --from-beginning --bootstrap-server localhost:9092
```

Take into account that the the host, port and topic used to setup the server should be used at the moment of providing the connection string to the deepstream application: <host>;<port>;<topic>.

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
python3 -m main --config_path configs/app_config.json --protolib_path /opt/nvidia/deepstream/deepstream-6.1/lib/libnvds_kafka_proto.so --connection_string localhost;9092;deepstream-topic
```