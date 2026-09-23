import json
from kafka import KafkaConsumer
from storage import table, append

if __name__ == "__main__":
    target = table()
    consumer = KafkaConsumer("keytrace.audit", bootstrap_servers="kafka:9092", group_id="iceberg-writer", auto_offset_reset="earliest", enable_auto_commit=False, value_deserializer=lambda value: json.loads(value))
    print("Audit writer ready", flush=True)
    try:
        while True:
            batch = consumer.poll(timeout_ms=1000, max_records=100)
            events = [message.value for messages in batch.values() for message in messages]
            if events:
                append(target, events)
                consumer.commit()  # Commit only after Iceberg's snapshot is durable.
                print(f"Stored {len(events)} audit events", flush=True)
    finally:
        consumer.close()
