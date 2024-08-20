
import time
import json
import random
from confluent_kafka import Producer

# Kafka configuration
conf = {
    'bootstrap.servers': 'localhost:9092',  # Replace with your Kafka broker address
    'client.id': 'cdc-simulator'
}

# Initialize the Kafka producer
producer = Producer(conf)

# Sample member data to simulate CDC events
sample_members = [
    {"member_id": "M001", "name": "John Doe", "email": "john.doe@example.com", "phone": "555-1234", "address": "123 Elm St"},
    {"member_id": "M002", "name": "Jane Smith", "email": "jane.smith@example.com", "phone": "555-5678", "address": "456 Oak St"},
    {"member_id": "M003", "name": "Alice Johnson", "email": "alice.johnson@example.com", "phone": "555-8765", "address": "789 Pine St"},
    {"member_id": "M004", "name": "Bob Brown", "email": "bob.brown@example.com", "phone": "555-4321", "address": "101 Maple St"}
]

# Operation types to simulate (INSERT, UPDATE, DELETE)
operations = ["INSERT", "UPDATE", "DELETE"]

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
        "ts": int(time.time() * 1000)  # Current timestamp in milliseconds
    }
    
    return cdc_event

def delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result. Triggered by poll() or flush(). """
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def simulate_cdc_events():
    topic = "cdc_retail_member"
    
    try:
        while True:
            # Generate a CDC event
            cdc_event = generate_cdc_event()
            
            # Serialize the event as a JSON string
            event_json = json.dumps(cdc_event)
            
            # Produce the message to Kafka
            producer.produce(topic, event_json, callback=delivery_report)
            
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
