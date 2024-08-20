package com.yourcompany.retail;

import com.github.javafaker.Faker;
import org.apache.avro.generic.GenericData;
import org.apache.avro.generic.GenericRecord;
import org.apache.avro.Schema;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import java.util.Random;
import java.util.concurrent.TimeUnit;

@Service
public class CdcProducer {

    private final KafkaTemplate<String, GenericRecord> kafkaTemplate;
    private final Faker faker;
    private final Random random;
    private static final String TOPIC = "cdc_retail_member";
    private static final String SCHEMA_STRING = "{\n" +
            "  \"fields\": [\n" +
            "    {\n" +
            "      \"name\": \"member_id\",\n" +
            "      \"type\": \"string\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"name\",\n" +
            "      \"type\": \"string\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"email\",\n" +
            "      \"type\": \"string\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"phone\",\n" +
            "      \"type\": \"string\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"address\",\n" +
            "      \"type\": \"string\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"operation\",\n" +
            "      \"type\": \"string\"\n" +
            "    },\n" +
            "    {\n" +
            "      \"name\": \"ts\",\n" +
            "      \"type\": {\n" +
            "        \"type\": \"long\",\n" +
            "        \"logicalType\": \"timestamp-millis\"\n" +
            "      }\n" +
            "    }\n" +
            "  ],\n" +
            "  \"name\": \"CdcRetailMember\",\n" +
            "  \"namespace\": \"com.yourcompany.retail\",\n" +
            "  \"type\": \"record\"\n" +
            "}";

    public CdcProducer(KafkaTemplate<String, GenericRecord> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
        this.faker = new Faker();
        this.random = new Random();
    }

    @PostConstruct
    public void simulateCdcEvents() {
        Schema schema = new Schema.Parser().parse(SCHEMA_STRING);

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

                kafkaTemplate.send(TOPIC, record.get("member_id").toString(), record);

                // Simulate delay between events
                TimeUnit.SECONDS.sleep(1);

            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    private String generateRandomString(int length) {
        return new Random().ints(48, 122)
                .filter(i -> (i < 58 || i > 64) && (i < 91 || i > 96))
                .limit(length)
                .collect(StringBuilder::new, StringBuilder::appendCodePoint, StringBuilder::append)
                .toString();
    }

    private String randomOperation() {
        String[] operations = {"INSERT", "UPDATE", "DELETE"};
        return operations[random.nextInt(operations.length)];
    }
}
