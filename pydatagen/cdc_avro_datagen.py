import time
import random
from confluent_kafka import SerializingProducer
from confluent_kafka.serialization import StringSerializer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from datetime import datetime
from faker import Faker
import string

# Kafka and Schema Registry configuration
conf = {
    'bootstrap.servers': 'localhost:9092',
    'schema.registry.url': 'http://localhost:9081'
}

# Avro schema as a JSON string
avro_schema_str = """
{
  "fields": [
    {
      "arg.properties": {
        "regex": "[A-Za-z0-9]+"
      },
      "doc": "Unique identifier for the retail member",
      "name": "member_id",
      "type": "string"
    },
    {
      "doc": "Full name of the retail member",
      "name": "name",
      "type": "string"
    },
    {
      "arg.properties": {
        "regex": "^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+$"
      },
      "doc": "Email address of the retail member",
      "name": "email",
      "type": "string"
    },
    {
      "doc": "Phone number of the retail member",
      "name": "phone",
      "type": "string"
    },
    {
      "doc": "Mailing address of the retail member",
      "name": "address",
      "type": "string"
    },
    {
      "name": "operation",
      "type": "string",
      "arg.properties": {
         "options": [
      	   "INSERT",
           "UPDATE",
           "DELETE"
        ]
      }
    },
    {
      "doc": "Timestamp of the change event",
      "name": "ts",
      "type": {
        "type": "long",
        "logicalType": "timestamp-millis"
      }
    }
  ],
  "name": "CdcRetailMember",
  "namespace": "com.yourcompany.retail",
  "type": "record"
}
"""

# Initialize Schema Registry client
schema_registry_client = SchemaRegistryClient({'url': conf['schema.registry.url']})

# Function to convert the CDC event to a dictionary that matches the Avro schema
def cdc_event_to_dict(cdc_event, ctx=None):
    return cdc_event

# Initialize Avro serializer
avro_serializer = AvroSerializer(
    schema_registry_client,
    avro_schema_str,
    cdc_event_to_dict
)

# Kafka producer configuration
producer_conf = {
    'bootstrap.servers': conf['bootstrap.servers'],
    'key.serializer': StringSerializer('utf_8'),
    'value.serializer': avro_serializer
}

def generate_random_string(length=8):
    """Generates a random string of given length with alphanumeric characters."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# Test the function
print(generate_random_string())


# Initialize the SerializingProducer with Kafka and Schema Registry configurations
producer = SerializingProducer(producer_conf)
# Initialize Faker for generating fake data
fake = Faker()


# Sample member data to simulate CDC events
sample_members = [
    {"member_id": "M001", "name": "John Doe", "email": "john.doe@example.com", "phone": "555-1234", "address": "123 Elm St"},
    {"member_id": "M002", "name": "Jane Smith", "email": "jane.smith@example.com", "phone": "555-5678", "address": "456 Oak St"},
    {"member_id": "M003", "name": "Alice Johnson", "email": "alice.johnson@example.com", "phone": "555-8765", "address": "789 Pine St"},
    {"member_id": "M004", "name": "Bob Brown", "email": "bob.brown@example.com", "phone": "555-4321", "address": "101 Maple St"}
]

# Operation types to simulate (INSERT, UPDATE, DELETE)
operations = ["INSERT", "UPDATE", "DELETE"]

def generate_fake_member_event():
    member_id = generate_random_string(8)  # Generates a string of 8 alphanumeric characters

    name = fake.name()  # Generates a realistic full name
    email = fake.email()  # Generates a realistic email address
    phone = fake.phone_number()  # Generates a realistic phone number
    address = fake.address().replace("\n", ", ")  # Generates a realistic mailing address
    operation = random.choice(["INSERT", "UPDATE", "DELETE"])  # Randomly selects an operation type
    
    # Generate the timestamp as milliseconds since epoch
    ts = int(datetime.now().timestamp() * 1000)

    # For DELETE operation, we might want to clear other fields except member_id
    if operation == "DELETE":
        name = ""
        email = ""
        phone = ""
        address = ""

    return {
        "member_id": member_id,
        "name": name,
        "email": email,
        "phone": phone,
        "address": address,
        "operation": operation,
        "ts": ts
    }

def generate_cdc_event():
    # Select a random member and operation type
    member = random.choice(sample_members)
    operation = random.choice(operations)
    
    # For UPDATE operation, modify some data
    if operation == "UPDATE":
        member["email"] = f"updated_{member['email']}"
    
    # For DELETE operation, remove the member data but keep the member_id
    if operation == "DELETE":
        member_data = {"member_id": member["member_id"]}
    else:
        member_data = member
    
    # Create a CDC event
    cdc_event = {
        "member_id": member_data["member_id"],
        "name": member_data.get("name", ""),
        "email": member_data.get("email", ""),
        "phone": member_data.get("phone", ""),
        "address": member_data.get("address", ""),
        "operation": operation,
        "ts": int(datetime.now().timestamp() * 1000)  # Convert current time to milliseconds
    }
    
    return cdc_event

def delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result. Triggered by poll() or flush(). """
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} to the Partition:[{msg.partition()}]")

def simulate_cdc_events():
    topic = "cdc_retail_member"
    
    try:
        while True:
            # Generate a CDC event
            cdc_event = generate_fake_member_event()
            
            # Produce the message to Kafka in Avro format
            producer.produce(topic=topic, key=cdc_event['member_id'], value=cdc_event, on_delivery=delivery_report)
            
            # Wait for events to be delivered
            producer.poll(0)
            
            # Simulate delay between events
            time.sleep(1)  # Adjust the sleep time to simulate more or fewer events per second
            
    except KeyboardInterrupt:
        pass
    finally:
        # Wait for any outstanding messages to be delivered and delivery reports to be received
        producer.flush()

if __name__ == "__main__":
    simulate_cdc_events()
