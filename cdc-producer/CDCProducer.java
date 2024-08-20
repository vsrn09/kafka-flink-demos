import org.apache.avro.generic.GenericData;
import org.apache.avro.generic.GenericRecord;
import org.apache.avro.Schema;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.clients.producer.Callback;
import org.apache.kafka.clients.producer.RecordMetadata;
import io.confluent.kafka.serializers.AbstractKafkaAvroSerDeConfig;
import io.confluent.kafka.serializers.KafkaAvroSerializer;
import io.confluent.kafka.schemaregistry.client.CachedSchemaRegistryClient;
import io.confluent.kafka.schemaregistry.client.SchemaRegistryClient;
import com.github.javafaker.Faker;

import java.util.Properties;
import java.util.Random;
import java.util.concurrent.TimeUnit;

public class CDCProducer {

    private static final String SCHEMA_STRING = "{\n" +
            "  \"fields\": [\n" +
            "    {\n" +
            "      \"name\": \"member_id\",\n" +
            "      \"type\": \"string\",\n" +
            "      \"arg.properties\": {\n" +
            "        \"regex\": \"[A-Za-z0-9]+\"\n" +
            "      },\n" +
            "      \"doc\": \"Unique identifier for the retail member\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"name\",\n" +
            "      \"type\": \"string\",\n" +
            "      \"doc\": \"Full name of the retail member\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"email\",\n" +
            "      \"type\": \"string\",\n" +
            "      \"arg.properties\": {\n" +
            "        \"regex\": \"^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+$\"\n" +
            "      },\n" +
            "      \"doc\": \"Email address of the retail member\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"phone\",\n" +
            "      \"type\": \"string\",\n" +
            "      \"doc\": \"Phone number of the retail member\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"address\",\n" +
            "      \"type\": \"string\",\n" +
            "      \"doc\": \"Mailing address of the retail member\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"operation\",\n" +
            "      \"type\": \"string\",\n" +
            "      \"arg.properties\": {\n" +
            "        \"options\": [\n" +
            "          \"INSERT\",\n" +
            "          \"UPDATE\",\n" +
            "          \"DELETE\"\n" +
            "        ]\n" +
            "      }\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"ts\",\n" +
            "      \"type\": {\n" +
            "        \"type\": \"long\",\n" +
            "        \"logicalType\": \"timestamp-millis\"\n" +
            "      },\n" +
            "      \"doc\": \"Timestamp of the change event\"\n" +
            "    }\n" +
            "  ],\n" +
            "  \"name\": \"CdcRetailMember\",\n" +
            "  \"namespace\": \"com.yourcompany.retail\",\n" +
            "  \"type\": \"record\"\n" +
            "}";

    public static void main(String[] args) {
        String schemaRegistryUrl = "http://localhost:9081";
        String bootstrapServers = "localhost:9092";
        String topic = "cdc_retail_member";

        // Initialize Schema Registry client
        SchemaRegistryClient schemaRegistry = new CachedSchemaRegistryClient(schemaRegistryUrl, 100);

        // Parse Avro schema
        Schema schema = new Schema.Parser().parse(SCHEMA_STRING);

        // Configure Kafka producer
        Properties props = new Properties();
        props.put("bootstrap.servers", bootstrapServers);
        props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
        props.put("value.serializer", KafkaAvroSerializer.class.getName());
        props.put(AbstractKafkaAvroSerDeConfig.SCHEMA_REGISTRY_URL_CONFIG, schemaRegistryUrl);

        KafkaProducer<String, GenericRecord> producer = new KafkaProducer<>(props);
        Faker faker = new Faker();
        Random random = new Random();

        // Event generation loop
        while (true) {
            try {
                GenericRecord record = new GenericData.Record(schema);
                record.put("member_id", generateRandomString(8));
                record.put("name", faker.name().fullName());
                record.put("email", faker.internet().emailAddress());
                record.put("phone", faker.phoneNumber().phoneNumber());
                record.put("address", faker.address().streetAddress().replace("\n", ", "));
                record.put("operation", randomOperation());
                record.put("ts", System.currentTimeMillis());

                if ("DELETE".equals(record.get("operation").toString())) {
                    record.put("name", "");
                    record.put("email", "");
                    record.put("phone", "");
                    record.put("address", "");
                }

                producer.send(new ProducerRecord<>(topic, record.get("member_id").toString(), record), new Callback() {
                    @Override
                    public void onCompletion(RecordMetadata metadata, Exception exception) {
                        if (exception != null) {
                            exception.printStackTrace();
                        } else {
                            System.out.println("Message delivered to topic " + metadata.topic() + " partition " + metadata.partition());
                        }
                    }
                });

                // Simulate delay between events
                TimeUnit.SECONDS.sleep(1);

            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                e.printStackTrace();
            }
        }

        producer.close();
    }

    private static String generateRandomString(int length) {
        return new Random().ints(48, 122)
                .filter(i -> (i < 58 || i > 64) && (i < 91 || i > 96))
                .limit(length)
                .collect(StringBuilder::new, StringBuilder::appendCodePoint, StringBuilder::append)
                .toString();
    }

    private static String randomOperation() {
        String[] operations = {"INSERT", "UPDATE", "DELETE"};
        return operations[new Random().nextInt(operations.length)];
    }
}
