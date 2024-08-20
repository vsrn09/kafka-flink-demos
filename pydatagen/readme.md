# Python emulator of the Confluent Datagen source connector

## Requirements:
- Python 3.8+
- Install python requirements (`python3 -m pip install -r requirements.txt`)

## Important:
 - This is a Kafka Producer and it does not use the Kafka Connect framework at all, also it is a single worker producer and `acks` is set to `0` (meaning, it will not wait for any acknowledgement from the broker)
 - The purpose of it is not to replace the [Datagen source connector](https://docs.confluent.io/kafka-connectors/datagen/current/overview.html) (far from that), but instead to be used for demo/development purposes when setting up a dummy-data producer where the data produced (message, headers and key) can be seen on the console and in the corresponding topic in the kafka cluster. It has an argument called `--dry-run` to display messages in the console instead of publishing to the Kafka cluster
 - Data is emulated based on the property `arg.properties` in the AVRO schema itself
 - See `resources/demo.avro` for a simple example of `arg.properties` and how to use it:
   - `iteration`: Generate a monotonic sequence of numbers
     - `start`: Starting number. However it also accept the strings `now`, `now_utc`, `now_ms` and `now_utc_ms` to start from the current (local or UTC) EPOCH timestamp (seconds or milliseconds)
     - `step`: Linear incrementing step. However it also accept the string `interval` where it will match with the number set on the command line argument of the same name
     ```
      "arg.properties": {
        "iteration": {
          "start": 0,
          "step": 1
        }
      }
     ```
     - Initial starting number would be the current local time in milliseconds, where the subsequent numbers would linearly increase as per `--interval` command line argument:
     ```
      "arg.properties": {
        "iteration": {
          "start": "now_ms",
          "step": "interval"
        }
      }
     ```
   - `regex`: Regular expression to generate a string
   ```
    "arg.properties": {
      "regex": "User_[0-9]{2}"
    }
   ```
   - `options`: List containing options to be randomly selected
   ```
    "arg.properties": {
      "options": [
        "Male",
        "Female",
        "Other"
      ]
    }
   ```
   - `range`: Generate a random number, between `min` and `max` arguments
   ```
    "arg.properties": {
      "range": {
        "min": -9999,
        "max": 9999
      }
    }
   ```
   - `arg.properties` can also be defined outside the field type defintion, see example on `credit_cards.avro`
   - In case `arg.properties` is not defined in the schema file, a random value will be picked (int/long: 1 to 9999, double: 0.00 to 99.99, boolean: true or false, string: 4 to 8 random alphanumeric chars)
   - Schema will be cleaned up of `arg.properties` before uploading it to the Schema Registry
 - Folder `resources/` was forked on 19-Nov-2022 (from https://github.com/confluentinc/kafka-connect-datagen/tree/master/src/main/resources)
 - Message headers can be set dynamically via:
   - Python script: create a function (def) called `headers()` (it must return an unested `Dict` object), see example on `headers/dynamic_000.py`
   - Statically: json file, see example on `headers/static_000.json`
   - **Important**: All header files must be inside the folder `headers/`

## Usage and help
```
usage:
  pydatagen.py [-h] [--client-id CLIENT_ID] 
               --schema-filename SCHEMA_FILENAME
               --topic TOPIC
               [--headers-filename HEADERS_FILENAME]
               [--keyfield KEYFIELD] [--key-json]
               [--bootstrap-servers BOOTSTRAP_SERVERS]
               [--partitioner {murmur2_random,murmur2,consistent_random,consistent,fnv1a_random,fnv1a,random}]
               [--schema-registry SCHEMA_REGISTRY]
               [--iterations ITERATIONS]
               [--interval INTERVAL]
               [--config-filename CONFIG_FILENAME]
               [--kafka-section KAFKA_SECTION]
               [--sr-section SR_SECTION]
               [--jitter_pct JITTER_PCT]
               [--jitter_min_ms JITTER_MIN_MS]
               [--jitter_max_ms JITTER_MAX_MS]
               [--silent]
               [--dry-run]

options:
  -h, --help            show this help message and exit
  --client-id CLIENT_ID
                        Producer's Client ID (if not set the default is pydatagen_XXXXXXXX, where XXXXXXXX is a unique id based on topic and
                        schema filename)
  --schema-filename SCHEMA_FILENAME
                        Avro schema file name (files must be inside the folder resources/)
  --keyfield KEYFIELD   Name of the field to be used as message key (required if argument --key-json is set)
  --key-json            Set key as JSON -> {{keyfield: keyfield_value}}
  --topic TOPIC         Topic name (required if argument --dry-run is not set)
  --headers-filename HEADERS_FILENAME
                        Select headers filename (files must be inside the folder headers/)
  --dry-run             Generate and display messages without having them publish
  --bootstrap-servers BOOTSTRAP_SERVERS
                        Bootstrap broker(s) (host[:port])
  --partitioner {murmur2_random,murmur2,consistent_random,consistent,fnv1a_random,fnv1a,random}
                        Set partitioner (default: murmur2_random)
  --schema-registry SCHEMA_REGISTRY
                        Schema Registry (http(s)://host[:port])
  --iterations ITERATIONS
                        Number of messages to be sent (default: 9999999999999)
  --interval INTERVAL   Max interval between messages in milliseconds (default: 500))
  --config-filename CONFIG_FILENAME
                        Select config filename for additional configuration, such as credentials (files must be inside the folder config/)
  --kafka-section KAFKA_SECTION
                        Section in the config file related to the Kafka cluster (e.g. kafka)
  --sr-section SR_SECTION
                        Section in the config file related to the Schema Registry (e.g. schema-registry)
  --silent              Do not display results on screen (not applicable to dry-run mode)
  --jitter_pct JITTER_PCT
                        Percentage of messages to be delayed (default is 0)
  --jitter_min_ms JITTER_MIN_MS
                        Min message delay, but only applicable if jitter percentage is > 0 (default is 100 ms)
  --jitter_max_ms JITTER_MAX_MS
                        Max message delay, but only applicable if jitter percentage is > 0 (default is 1000 ms)
```

## Examples:
### Input (dry-run mode)
```
python3 pydatagen.py --schema-filename gaming_players.avro --dry-run \
                     --headers-filename dynamic_000.py --keyfield player_id \
                     --key-json --interval 1000 --iterations 10
```
### Output (dry-run mode)
```
Producing 10 messages in dry-run mode. ^C to exit.

message #1: {'player_id': 1072, 'player_name': 'Talbot Cashell', 'ip': '104.16.237.57'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1072}

message #2: {'player_id': 1053, 'player_name': 'Cirstoforo Joblin', 'ip': '37.136.192.70'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1053}

message #3: {'player_id': 1047, 'player_name': 'Cort Bainbridge', 'ip': '26.45.199.135'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1047}

message #4: {'player_id': 1041, 'player_name': 'Fitz Ballin', 'ip': '61.160.45.31'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1041}

message #5: {'player_id': 1092, 'player_name': 'Faye Beaument', 'ip': '77.208.184.143'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1092}

message #6: {'player_id': 1034, 'player_name': 'Jori Ottiwill', 'ip': '44.125.117.30'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1034}

message #7: {'player_id': 1009, 'player_name': 'Winny Cadigan', 'ip': '68.145.84.22'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1009}

message #8: {'player_id': 1059, 'player_name': 'Riva Rossant', 'ip': '64.39.185.31'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1059}

message #9: {'player_id': 1051, 'player_name': 'Nathaniel Hallowell', 'ip': '206.228.92.173'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1051}

message #10: {'player_id': 1095, 'player_name': 'Chryste Wren', 'ip': '141.46.127.99'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1095}
```

### Input (local Kafka/SR)
```
python3 pydatagen.py --schema-filename gaming_players.avro \
                     --headers-filename dynamic_000.py --keyfield player_id \
                     --key-json --interval 1000 --iterations 10 --topic test2
```
### Output (local Kafka/SR)
```
Producing 10 messages to topic 'test2' via client.id 'pydatagen_a7cc48eb'. ^C to exit.

message #1: {'player_id': 1079, 'player_name': 'Nertie Zuker', 'ip': '219.151.0.93'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1079}
> Message successfully produced to test2: Partition = 0, Offset = 391

message #2: {'player_id': 1020, 'player_name': 'Pattin Eringey', 'ip': '66.106.114.58'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1020}
> Message successfully produced to test2: Partition = 0, Offset = 392

message #3: {'player_id': 1006, 'player_name': 'Brenna Woolfall', 'ip': '46.152.206.98'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1006}
> Message successfully produced to test2: Partition = 0, Offset = 393

message #4: {'player_id': 1053, 'player_name': 'Cirstoforo Joblin', 'ip': '37.136.192.70'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1053}
> Message successfully produced to test2: Partition = 0, Offset = 394

message #5: {'player_id': 1099, 'player_name': 'Raychel Roset', 'ip': '183.237.217.217'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1099}
> Message successfully produced to test2: Partition = 0, Offset = 395

message #6: {'player_id': 1062, 'player_name': 'Aryn Haskell', 'ip': '215.235.104.14'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1062}
> Message successfully produced to test2: Partition = 0, Offset = 396

message #7: {'player_id': 1006, 'player_name': 'Brenna Woolfall', 'ip': '46.152.206.98'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1006}
> Message successfully produced to test2: Partition = 0, Offset = 397

message #8: {'player_id': 1058, 'player_name': 'Aldrich MacVay', 'ip': '198.1.226.227'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1058}
> Message successfully produced to test2: Partition = 0, Offset = 398

message #9: {'player_id': 1036, 'player_name': 'Zechariah Wrate', 'ip': '11.107.127.127'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1036}
> Message successfully produced to test2: Partition = 0, Offset = 399

message #10: {'player_id': 1100, 'player_name': 'Heindrick Ravenscroft', 'ip': '165.19.12.241'}
headers: {'program': 'python', 'version': '3.10.8', 'node': 'P3W32CDKHC', 'environment': 'test'}
key: {"player_id": 1100}

Flushing messages...
> Message successfully produced to test2: Partition = 0, Offset = 400
```

### Input (Confluent Cloud)
```
python3 pydatagen.py --schema-filename users_schema.avro \
                     --topic demo_users \
                     --keyfield userid \
                     --iterations 10 \
                     --config-filename cc_config.ini \
                     --kafka-section kafka \
                     --sr-section schema-registry
```

Where ```cc_config.ini``` is a file as shown below and located at ```config/cc_config.ini```:
```
[kafka]
bootstrap.servers = {{ host:port }}  --> if set, it will override the --bootstrap-servers cli argument
security.protocol = SASL_SSL
sasl.mechanisms = PLAIN
sasl.username = {{ CLUSTER_API_KEY }}
sasl.password = {{ CLUSTER_API_SECRET }}
[schema-registry]
url = {{ http(s)://url:port }}  --> if set, it will override the --schema-registry cli argument
basic.auth.user.info = {{ SR_API_KEY }}:{{ SR_API_SECRET }}
```

### Output (Confluent Cloud)
```
Producing 10 messages to topic 'demo_users' via client.id 'pydatagen_2f92fe12'. ^C to exit.

message #1: {'registertime': 1510578677035, 'userid': 'User_1', 'regionid': 'Region_5', 'gender': 'FEMALE'}
key: User_1
message #2: {'registertime': 1511882009729, 'userid': 'User_5', 'regionid': 'Region_2', 'gender': 'MALE'}
key: User_5
message #3: {'registertime': 1494577280510, 'userid': 'User_4', 'regionid': 'Region_1', 'gender': 'FEMALE'}
key: User_4
> Message successfully produced to demo_users: Partition = 5, Offset = None

> Message successfully produced to demo_users: Partition = 0, Offset = None

> Message successfully produced to demo_users: Partition = 3, Offset = None

message #4: {'registertime': 1505497202196, 'userid': 'User_4', 'regionid': 'Region_9', 'gender': 'OTHER'}
key: User_4
> Message successfully produced to demo_users: Partition = 3, Offset = None

message #5: {'registertime': 1512624021620, 'userid': 'User_7', 'regionid': 'Region_7', 'gender': 'FEMALE'}
key: User_7
> Message successfully produced to demo_users: Partition = 3, Offset = None

message #6: {'registertime': 1516496385918, 'userid': 'User_4', 'regionid': 'Region_7', 'gender': 'MALE'}
key: User_4
> Message successfully produced to demo_users: Partition = 3, Offset = None

message #7: {'registertime': 1496322719875, 'userid': 'User_1', 'regionid': 'Region_4', 'gender': 'MALE'}
key: User_1
> Message successfully produced to demo_users: Partition = 0, Offset = None

message #8: {'registertime': 1509869837448, 'userid': 'User_2', 'regionid': 'Region_2', 'gender': 'FEMALE'}
key: User_2
> Message successfully produced to demo_users: Partition = 0, Offset = None

message #9: {'registertime': 1502462026766, 'userid': 'User_5', 'regionid': 'Region_1', 'gender': 'FEMALE'}
key: User_5
> Message successfully produced to demo_users: Partition = 5, Offset = None

message #10: {'registertime': 1493905105632, 'userid': 'User_1', 'regionid': 'Region_7', 'gender': 'OTHER'}
key: User_1

Flushing messages...
> Message successfully produced to demo_users: Partition = 0, Offset = None
```

# TBD
 - Implement a stateful producer using Markov models

# External References
Confluent Datagen Source Connector: https://docs.confluent.io/kafka-connectors/datagen/current/overview.html

Check out [Confluent's Developer portal](https://developer.confluent.io), it has free courses, documents, articles, blogs, podcasts and so many more content to get you up and running with a fully managed Apache Kafka service.

Disclaimer: I work for Confluent :wink: