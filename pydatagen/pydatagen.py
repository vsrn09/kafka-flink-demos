# -*- coding: utf-8 -*-
#
# Copyright 2022 Confluent Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Python emulator of the Confluent Datagen source connector
# https://docs.confluent.io/kafka-connectors/datagen/current/overview.html


import os
import re
import sys
import json
import time
import exrex
import random
import hashlib
import logging
import argparse
import datetime
import avro.schema
import commentjson
import configparser

from functools import lru_cache
from importlib import import_module
from confluent_kafka import Producer
from confluent_kafka.serialization import (
    SerializationContext,
    MessageField,
)
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

from utils import GracefulShutdown, sys_exc


# Global Variables
FILE_APP = os.path.split(__file__)[-1]
FOLDER_APP = os.path.dirname(__file__)
FOLDER_HEADERS = "headers"
FOLDER_SCHEMAS = "resources"
FOLDER_CONFIG = "config"

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d [%(levelname)s]: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


# General functions
def real_sleep(
    millisecs: int,
    start_time: float,
):
    """Sleep function to take into account the elapsed time in between messages generated/published"""
    total_secs = millisecs / 1000 - (time.time() - start_time)
    if total_secs > 0:
        time.sleep(total_secs)


def get_config_section_data(
    config_filename: str,
    config_data: configparser.ConfigParser,
    section: str,
) -> dict:
    """Get section data inside the config file"""
    if section is None:
        return dict()
    elif section in config_data.sections():
        return dict(config_data[section])
    else:
        logging.critical(
            f'{FILE_APP}: error: when processing config file "{config_filename}": section "{section}" not found'
        )
        sys.exit(-1)


class AvroParser:
    @staticmethod
    @lru_cache
    def _get_field_type(field_type: str):
        """Internal method (idempotent) to return Python's equivalent type, None if no match"""
        if field_type in ["int", "long"]:
            return int
        elif field_type in ["float", "decimal", "bytes", "double"]:
            return float
        elif field_type == "boolean":
            return bool
        elif field_type == "array":
            return list
        elif field_type == "string":
            return str

    @staticmethod
    @lru_cache
    def _get_static_headers(filename: str) -> dict:
        """Internal method (idempotent) to return static message headers"""
        full_filename = os.path.join(FOLDER_APP, FOLDER_HEADERS, filename)
        if os.path.isfile(full_filename):
            with open(full_filename, "r") as f:
                return commentjson.loads(f.read())
        else:
            logging.critical(
                f"{FILE_APP}: error: Static headers filename not found: {full_filename}"
            )
            sys.exit(-1)

    @staticmethod
    @lru_cache
    def _get_dynamic_headers_module(filename: str):
        """Internal method (idempotent) to return dynamic message headers' module"""
        full_filename = os.path.join(FOLDER_APP, FOLDER_HEADERS, filename)
        if os.path.isfile(full_filename):
            return import_module(f"{FOLDER_HEADERS}.{filename[:-3]}")
        else:
            logging.critical(
                f"{FILE_APP}: error: Dynamic headers filename not found: {full_filename}"
            )
            sys.exit(-1)

    @staticmethod
    def data_dict(
        data: dict,
        ctx,
    ) -> dict:
        """
        Returns a dict representation of a data instance for serialization.
        Args:
            data (dict): payload data
            ctx (SerializationContext): Metadata pertaining to the serialization
                operation.
        Returns:
            dict: Dict populated with user attributes to be serialized.
        """
        return dict(data)

    @staticmethod
    def delivery_report(err, msg):
        """
        Reports the failure or success of a message delivery.
        Args:
            err (KafkaError): The error that occurred on None on success.
            msg (Message): The message that was produced or failed.
        Note:
            In the delivery report callback the Message.key() and Message.value()
            will be the binary format as encoded by any configured Serializers and
            not the same object that was passed to produce().
            If you wish to pass the original object(s) for key and value to delivery
            report callback we recommend a bound callback or lambda where you pass
            the objects along.
        """

        if err is not None:
            logging.error(
                f"<Callback> Delivery failed for Data record {msg.key()}: {err}"
            )
        else:
            logging.info(
                f"<Callback> Message successfully produced to Topic '{msg.topic()}': Key = {None if msg.key() is None else msg.key().decode()}, Partition = {msg.partition()}, Offset = {msg.offset()}"
            )

    @staticmethod
    def _get_type(field_type):
        """Internal method to return field type, pick a random one in case of Union"""
        if isinstance(field_type, list):
            return random.choice(field_type)
        else:
            return field_type

    def __init__(self, avro_schema_filename: str) -> None:
        self.payload_iteration_cache = dict()  # In case of arg.properties INTERATION
        self.keyfield_type = str  # default

        # Read avro schema file (throws exception in case of error)
        if os.path.isfile(avro_schema_filename):
            try:
                with open(avro_schema_filename, "r") as f:
                    self.avro_schema_original = commentjson.loads(f.read())

            except Exception:
                logging.critical(
                    f'{FILE_APP}: error: when processing schema file "{avro_schema_filename}": {sys_exc(sys.exc_info())}'
                )
                sys.exit(-1)
        else:
            logging.critical(
                f"{FILE_APP}: error: Schema filename not found: {avro_schema_filename}"
            )
            sys.exit(-1)

        # Validate avro schema (throws exception in case of error)
        avro.schema.parse(json.dumps(self.avro_schema_original))

        # Cleanup schema
        self.avro_schema = self._cleanup_schema(self.avro_schema_original)

    def _cleanup_schema(self, schema):
        """
        Remove arg.properties from schema (recurring function)
        """
        if isinstance(schema, dict):
            avro_schema = dict()
            for key, value in schema.items():
                if key != "arg.properties":
                    if isinstance(value, list):
                        avro_schema[key] = list()
                        for n in value:
                            avro_schema[key].append(self._cleanup_schema(n))
                    else:
                        avro_schema[key] = self._cleanup_schema(value)
            return avro_schema
        else:
            return schema

    def set_headers(self, headers_filename: str) -> dict:
        """Internal method to return message headers"""
        try:
            if headers_filename.lower().endswith(".py"):
                # Import python module and get dict value from method headers() -> dict:
                return self._get_dynamic_headers_module(headers_filename).headers()
            else:
                return self._get_static_headers(headers_filename)
        except Exception:
            logging.critical(
                f'{FILE_APP}: error: when processing headers file "{headers_filename}": {sys_exc(sys.exc_info())}'
            )
            sys.exit(-1)

    def set_key(self, message: dict, key_json: bool, keyfield: str):
        """Set message key"""
        message_key = message[keyfield]
        if key_json:
            message_key = json.dumps({keyfield: message_key})
        else:
            if self.keyfield_type == bool:
                message_key = "true" if message_key else "false"
            elif self.keyfield_type == list:
                message_key = "[" + ",".join(str(item) for item in message_key) + "]"
            else:
                message_key = str(message_key)
        return message_key

    def generate_payload(
        self,
        avro_schema: dict,
        keyfield: str = None,
        is_recurring: bool = False,
        args=None,
    ) -> dict:
        """
        Generate random payload as per AVRO schema
        Args:
            avro_schema (dict): Avro schema with arg.properties
            keyfield (str): Key field name
            is_recurring (bool): Do not set this value, it is used in recurrency cases (array type)
        Returns:
            dict: payload
        """

        # Generated payload
        payload = dict()

        # Check for arg.properties defined on the 1st level of the schema
        #   if so randomly chose options (ONLY OPTIONS IS PARSED FOR NOW)
        args_properties = avro_schema.get("arg.properties")
        if isinstance(args_properties, dict):
            if isinstance(args_properties.get("options"), list):
                payload = random.choice(args_properties.get("options"))

        # Generate payload data/fields types
        payload_fields = dict()
        for field in avro_schema.get("fields", list()):
            if isinstance(field, dict):
                field_name = field.get("name")

                if field_name is not None:
                    field_type = field.get("type")

                    if type(field_type) in [str, list]:
                        payload_fields[field_name] = {
                            "type": self._get_type(field_type),
                            "scale": field.get("scale"),
                            "arg.properties": field.get("arg.properties"),
                        }

                    elif isinstance(field_type, dict):
                        field_type_type = self._get_type(field_type.get("type"))
                        if not is_recurring and keyfield == field_name:
                            self.keyfield_type = self._get_field_type(field_type_type)

                        # arg.properties defined on the field level
                        args_properties = field.get("arg.properties")

                        # arg.properties defined on the field type level
                        if args_properties is None:
                            args_properties = field_type.get("arg.properties")

                        if args_properties is None:
                            args_properties = dict()

                        if field_type_type == "array":
                            field_items = field_type.get("items")
                            if isinstance(field_items, dict):
                                min_items = args_properties.get("length", dict()).get(
                                    "min",
                                    1,
                                )
                                max_items = args_properties.get("length", dict()).get(
                                    "max",
                                    1,
                                )
                                payload[field_name] = list()
                                for _ in range(random.randint(min_items, max_items)):
                                    payload[field_name].append(
                                        self.generate_payload(
                                            {
                                                "fields": field_items.get(
                                                    "fields", list()
                                                ),
                                                "arg.properties": field_items.get(
                                                    "arg.properties"
                                                ),
                                            },
                                            is_recurring=True,
                                            args=args,
                                        )
                                    )

                        elif field_type_type == "record":
                            payload[field_name] = self.generate_payload(
                                {
                                    "fields": field_type.get("fields", list()),
                                    "arg.properties": field_type.get("arg.properties"),
                                },
                                is_recurring=True,
                                args=args,
                            )

                        else:
                            if isinstance(field_type_type, str):
                                payload_fields[field_name] = {
                                    "type": field_type_type,
                                    "arg.properties": args_properties,
                                    "scale": field_type.get("scale"),
                                }

        # Generate random data
        for field_name, params in payload_fields.items():
            if payload.get(field_name) is None:
                payload[field_name] = None

                # No arg.properties defined, set one
                if not (
                    isinstance(params.get("arg.properties"), dict)
                    and len(params.get("arg.properties"))
                ):
                    missing_field_type = self._get_field_type(
                        payload_fields[field_name].get("type")
                    )
                    if missing_field_type == int:
                        params["arg.properties"] = {
                            "range": {
                                "min": 1,
                                "max": 9999,
                            }
                        }
                    elif missing_field_type == float:
                        params["scale"] = 2
                        params["arg.properties"] = {
                            "range": {
                                "min": 0,
                                "max": 99.99,
                            }
                        }
                    elif missing_field_type == str:
                        params["arg.properties"] = {
                            "regex": "[a-zA-Z1-9]{4,8}",
                        }
                    elif missing_field_type == bool:
                        params["arg.properties"] = {
                            "options": [
                                True,
                                False,
                            ]
                        }
                    else:  # set none, in case of array
                        params["arg.properties"] = {None: None}

                args_properties_type = next(iter(params.get("arg.properties")))

                # OPTIONS
                if args_properties_type == "options":
                    if isinstance(params["arg.properties"][args_properties_type], list):
                        payload[field_name] = random.choice(
                            params["arg.properties"][args_properties_type]
                        )

                # INTERATION
                elif args_properties_type == "iteration":
                    if isinstance(params["arg.properties"][args_properties_type], dict):
                        iteration_start = params["arg.properties"][
                            args_properties_type
                        ].get("start", 0)
                        ## This block is not part of the DataGen source connector, it is applicable only to pydatagen ###
                        if isinstance(iteration_start, str):
                            if iteration_start.lower() == "now":
                                iteration_start = int(
                                    datetime.datetime.now().timestamp()
                                )
                            elif iteration_start.lower() == "now_utc":
                                iteration_start = int(
                                    datetime.datetime.utcnow().timestamp()
                                )
                            elif iteration_start.lower() == "now_ms":
                                iteration_start = int(
                                    datetime.datetime.now().timestamp() * 1000
                                )
                            elif iteration_start.lower() == "now_utc_ms":
                                iteration_start = int(
                                    datetime.datetime.utcnow().timestamp() * 1000
                                )
                            else:
                                iteration_start = 0
                        ##################################################################################################
                        iteration_step = params["arg.properties"][
                            args_properties_type
                        ].get("step", 1)
                        ## This block is not part of the DataGen source connector, it is applicable only to pydatagen ###
                        if isinstance(iteration_step, str):
                            if iteration_step.lower() == "interval":
                                iteration_step = int(args.interval)
                            else:
                                iteration_step = 1
                        ##################################################################################################
                        if self.payload_iteration_cache.get(field_name) is None:
                            self.payload_iteration_cache[field_name] = iteration_start
                        else:
                            self.payload_iteration_cache[field_name] += iteration_step
                        payload[field_name] = self.payload_iteration_cache[field_name]

                # RANGE
                elif args_properties_type == "range":
                    if isinstance(params["arg.properties"][args_properties_type], dict):
                        range_min = params["arg.properties"][args_properties_type].get(
                            "min", 0
                        )
                        range_max = params["arg.properties"][args_properties_type].get(
                            "max", 1
                        )
                        if isinstance(range_min, int) and isinstance(range_max, int):
                            payload[field_name] = random.randrange(range_min, range_max)
                        else:
                            value = random.uniform(range_min, range_max)
                            if isinstance(params.get("scale"), int):
                                value = round(value, params.get("scale"))
                            payload[field_name] = value

                # REGEX
                elif args_properties_type == "regex":
                    if isinstance(params["arg.properties"][args_properties_type], str):
                        payload[field_name] = exrex.getone(
                            params["arg.properties"][args_properties_type]
                        )

        return payload


def main(args):
    avro_schema_filename = os.path.join(
        FOLDER_APP,
        FOLDER_SCHEMAS,
        args.schema_filename,
    )
    avsc = AvroParser(avro_schema_filename)

    if args.dry_run:
        logging.info(
            f"Producing {args.iterations} messages in dry-run mode. ^C to exit."
        )
        try:
            for msg in range(args.iterations):
                start_time = time.time()
                message = avsc.generate_payload(
                    avsc.avro_schema_original,
                    keyfield=args.keyfield,
                    args=args,
                )
                logging.info(f"message #{msg+1}: {message}")

                # Set headers
                if args.headers_filename:
                    message_headers = avsc.set_headers(args.headers_filename)
                    logging.info(f"headers: {message_headers}")

                # Set key
                if message.get(args.keyfield):
                    message_key = avsc.set_key(message, args.key_json, args.keyfield)
                    logging.info(f"key: {message_key}")

                real_sleep(args.interval, start_time)

        except KeyboardInterrupt:
            logging.warning("CTRL-C pressed by user")

    else:
        producer = None
        try:
            # Read config file (if any)
            schema_registry_conf_additional = dict()
            kafka_conf_additional = dict()
            if args.config_filename:
                config_filename = os.path.join(
                    FOLDER_APP,
                    "config",
                    args.config_filename,
                )
                if os.path.exists(config_filename):
                    try:
                        config_data = configparser.ConfigParser()
                        config_data.read(config_filename)
                        schema_registry_conf_additional = get_config_section_data(
                            args.config_filename,
                            config_data,
                            args.sr_section,
                        )
                        kafka_conf_additional = get_config_section_data(
                            args.config_filename,
                            config_data,
                            args.kafka_section,
                        )
                    except Exception:
                        logging.critical(
                            f'{FILE_APP}: error: when processing config file "{args.config_filename}": {sys_exc(sys.exc_info())}'
                        )
                        sys.exit(-1)
                else:
                    logging.critical(
                        f'{FILE_APP}: error: when processing config file "{config_filename}": file not found'
                    )
                    sys.exit(-1)

            # Schema Registry config
            schema_registry_conf = {
                "url": args.schema_registry,
            }
            schema_registry_conf.update(
                schema_registry_conf_additional
            )  # override with the additional config
            schema_registry_client = SchemaRegistryClient(schema_registry_conf)

            # Client ID
            if args.client_id is None:
                client_id = f"{os.path.splitext(FILE_APP)[0]}_{hashlib.sha1(f'{args.topic}@{args.schema_filename}'.encode()).hexdigest()[:8]}"
            else:
                # Sanitise client id
                client_id = re.sub(
                    "[^a-z0-9\.\_\-]",
                    "",
                    args.client_id,
                    flags=re.IGNORECASE,
                )

            # Producer config
            kafka_conf = {
                "acks": 0,
                "bootstrap.servers": args.bootstrap_servers,
                "client.id": client_id[:255],
                "partitioner": args.partitioner,
            }
            kafka_conf.update(
                kafka_conf_additional
            )  # override with the additional config

            producer = Producer(kafka_conf)
            avro_serializer = AvroSerializer(
                schema_registry_client,
                json.dumps(avsc.avro_schema),
                to_dict=avsc.data_dict,
            )

            logging.info(
                f"""Producing {args.iterations} messages to topic '{args.topic}' via client.id '{kafka_conf["client.id"]}'. ^C to exit."""
            )

            gs = GracefulShutdown(producer)

            msg = 0
            jitter_queue = dict()
            jitter_pct = args.jitter_pct / 100
            jitter_min_ms, jitter_max_ms = (args.jitter_max_ms, args.jitter_min_ms) if args.jitter_min_ms > args.jitter_max_ms else (args.jitter_min_ms, args.jitter_max_ms)
            while msg < args.iterations or len(jitter_queue.keys()) > 0:
                msg += 1
                start_time = time.time()

                with gs as _:
                    try:
                        if msg < args.iterations:
                            message = avsc.generate_payload(
                                avsc.avro_schema_original,
                                keyfield=args.keyfield,
                                args=args,
                            )

                            producer_args = {
                                "topic": args.topic,
                                "value": avro_serializer(
                                    message,
                                    SerializationContext(
                                        args.topic,
                                        MessageField.VALUE,
                                    ),
                                ),
                            }

                            if not args.silent:
                                producer_args["on_delivery"] = avsc.delivery_report
                                logging.info(f"message #{msg+1}: {message}")

                            # Set headers
                            if args.headers_filename:
                                message_headers = avsc.set_headers(args.headers_filename)
                                producer_args["headers"] = message_headers
                                if not args.silent:
                                    logging.info(f"headers: {message_headers}")

                            # Set key
                            if message.get(args.keyfield):
                                message_key = avsc.set_key(
                                    message,
                                    args.key_json,
                                    args.keyfield,
                                )
                                producer_args["key"] = message_key
                                if not args.silent:
                                    logging.info(f"key: {message_key}")

                            # Publish message
                            delayed_message = False
                            if jitter_pct > 0:
                                if jitter_pct > random.random():
                                    delayed_message = True
                                    send_at = time.time() + random.randint(jitter_min_ms, jitter_max_ms) / 1000
                                    if "headers" not in producer_args.keys():
                                        producer_args["headers"] = list()
                                    producer_args["headers"].append(("delayed_message", "true"))
                                    jitter_queue[send_at] = producer_args
                                    logging.info(f">>> Delayed message, to be sent after {send_at}: {producer_args['key']} {message}")

                            if not delayed_message:
                                producer.poll(0.0)
                                producer.produce(**producer_args)
                                real_sleep(args.interval, start_time)

                        # Check for delayed messages
                        for send_at in [m for m in jitter_queue.keys() if time.time() > m]:
                            start_time = time.time()
                            producer.poll(0.0)
                            logging.info(f"<<< Sending delayed message ({send_at}): {jitter_queue[send_at]['key']}")
                            producer.produce(**jitter_queue[send_at])
                            jitter_queue.pop(send_at)
                            real_sleep(args.interval, start_time)

                    except KeyboardInterrupt:
                        logging.warning("CTRL-C pressed by user")
                        jitter_queue = dict()
                        msg = args.iterations + 1
                        break

                    except ValueError:
                        logging.error(
                            f"Invalid input, discarding record: {sys_exc(sys.exc_info())}"
                        )
                        real_sleep(args.interval, start_time)

            logging.info("Flushing messages...")
            producer.flush()

        except Exception:
            logging.critical(
                f"{FILE_APP}: error: when publishing messages: {sys_exc(sys.exc_info())}"
            )
            sys.exit(-1)


if __name__ == "__main__":
    PARTITIONERS = [
        "murmur2_random",
        "murmur2",
        "consistent_random",
        "consistent",
        "fnv1a_random",
        "fnv1a",
        "random",
    ]
    parser = argparse.ArgumentParser(
        description="Python emulator of the Kafka source connector Datagen"
    )
    parser.add_argument(
        "--client-id",
        dest="client_id",
        type=str,
        help=f"Producer's Client ID (if not set the default is {os.path.splitext(FILE_APP)[0]}_XXXXXXXX, where XXXXXXXX is a unique id based on topic and schema filename)",
        default=None,
    )
    parser.add_argument(
        "--schema-filename",
        help=f"Avro schema file name (files must be inside the folder {FOLDER_SCHEMAS}/)",
        dest="schema_filename",
        required=True,
        type=str,
    )
    parser.add_argument(
        "--keyfield",
        help="Name of the field to be used as message key (required if argument --key-json is set)",
        dest="keyfield",
        type=str,
        default=None,
        required="--key-json" in sys.argv,
    )
    parser.add_argument(
        "--key-json",
        dest="key_json",
        action="store_true",
        help="Set key as JSON -> {{keyfield: keyfield_value}}",
    )
    parser.add_argument(
        "--topic",
        help="Topic name (required if argument --dry-run is not set)",
        dest="topic",
        required="--dry-run" not in sys.argv,
        type=str,
    )
    parser.add_argument(
        "--headers-filename",
        dest="headers_filename",
        type=str,
        help=f"Select headers filename (files must be inside the folder {FOLDER_HEADERS}/)",
        default=None,
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Generate and display messages without having them publish",
    )
    parser.add_argument(
        "--bootstrap-servers",
        dest="bootstrap_servers",
        default="localhost:9092",
        help="Bootstrap broker(s) (host[:port])",
        type=str,
    )
    parser.add_argument(
        "--partitioner",
        dest="partitioner",
        help=f"Set partitioner (default: {PARTITIONERS[0]})",
        type=str,
        default=PARTITIONERS[0],
        choices=PARTITIONERS,
    )
    parser.add_argument(
        "--schema-registry",
        help="Schema Registry (http(s)://host[:port])",
        dest="schema_registry",
        default="http://localhost:8081",
        type=str,
    )
    parser.add_argument(
        "--iterations",
        help="Number of messages to be sent (default: 9999999999999)",
        dest="iterations",
        default=9999999999999,
        type=int,
    )
    parser.add_argument(
        "--interval",
        help="Max interval between messages in milliseconds (default: 500))",
        dest="interval",
        default=500,
        type=int,
    )
    parser.add_argument(
        "--config-filename",
        dest="config_filename",
        type=str,
        help=f"Select config filename for additional configuration, such as credentials (files must be inside the folder {FOLDER_CONFIG}/)",
        default=None,
    )
    parser.add_argument(
        "--kafka-section",
        dest="kafka_section",
        type=str,
        help=f"Section in the config file related to the Kafka cluster (e.g. kafka)",
        default=None,
    )
    parser.add_argument(
        "--sr-section",
        dest="sr_section",
        type=str,
        help=f"Section in the config file related to the Schema Registry (e.g. schema-registry)",
        default=None,
    )
    parser.add_argument(
        "--silent",
        dest="silent",
        action="store_true",
        help="Do not display results on screen (not applicable to dry-run mode)",
    )
    parser.add_argument(
        "--jitter_pct",
        dest="jitter_pct",
        type=int,
        help="Percentage of messages to be delayed (default is 0)",
        default=0,
    )
    parser.add_argument(
        "--jitter_min_ms",
        dest="jitter_min_ms",
        type=int,
        help="Min message delay, but only applicable if jitter percentage is > 0 (default is 100 ms)",
        default=100,
    )
    parser.add_argument(
        "--jitter_max_ms",
        dest="jitter_max_ms",
        type=int,
        help="Max message delay, but only applicable if jitter percentage is > 0 (default is 1000 ms)",
        default=1000,
    )
    main(parser.parse_args())
