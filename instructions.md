-- Source Table with Optimized Watermark
CREATE TABLE cdc_retail_member (
    `member_id` STRING,
    `name` STRING,
    `email` STRING,
    `phone` STRING,
    `address` STRING,
    `operation` STRING,
    `ts` TIMESTAMP(3),
    WATERMARK FOR ts AS ts - INTERVAL '1' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'cdc_retail_member',
    'scan.startup.mode' = 'earliest-offset',
    'properties.bootstrap.servers' = 'broker:9094',
    'properties.group.id' = 'flink_cdc_group',
    'key.fields' = 'member_id',
	'properties.request.timeout.ms' = '60000',
	'properties.retry.backoff.ms' = '1000',
    'key.format' = 'raw',
    'value.format' = 'avro-confluent',
    'value.avro-confluent.schema-registry.url' = 'http://schema-registry:9081'
);

-- Transformation with Smaller Window Size
CREATE TABLE oracle_banking_payload (
    `request_id` STRING,
    `payload` STRING,
    `operation` STRING,
    `window_start` TIMESTAMP(3),
    `window_end` TIMESTAMP(3),
    `update_count` BIGINT
) WITH (
    'connector' = 'kafka',
    'topic' = 'oracle_banking_payload',
    'scan.startup.mode' = 'earliest-offset',
    'properties.bootstrap.servers' = 'broker:9094',
    'key.fields' = 'request_id',
    'key.format' = 'raw',
    'value.format' = 'json'
);

INSERT INTO oracle_banking_payload
SELECT 
    CONCAT('REQ_', member_id, '_', CAST(TUMBLE_START(ts, INTERVAL '5' SECOND) AS STRING)) AS request_id,
    CONCAT(
        '{"memberId":"', member_id, '",',
        '"name":"', MAX(name), '",',
        '"email":"', MAX(email), '",',
        '"phone":"', MAX(phone), '",',
        '"address":"', MAX(address), '"}'
    ) AS payload,
    operation,
    TUMBLE_START(ts, INTERVAL '5' SECOND) AS window_start,
    TUMBLE_END(ts, INTERVAL '5' SECOND) AS window_end,
    COUNT(*) AS update_count
FROM cdc_retail_member
WHERE operation IN ('INSERT', 'UPDATE')
GROUP BY member_id, operation, TUMBLE(ts, INTERVAL '5' SECOND);


-- Error Handling with Non-200 HTTP Response Code
CREATE TABLE error_queue (
    `request_id` STRING,
    `error_message` STRING,
    `payload` STRING,
    `operation` STRING,
    `window_start` TIMESTAMP(3),
    `window_end` TIMESTAMP(3)
    --`http_status_code` INT
) WITH (
    'connector' = 'kafka',
    'topic' = 'error_queue',
    'scan.startup.mode' = 'earliest-offset',
    'properties.bootstrap.servers' = 'broker:9094',
    'key.fields' = 'request_id',
    'key.format' = 'raw',
    'value.format' = 'json'
);

CREATE TABLE oracle_api_sink (
    `request_id` STRING,
    `payload` STRING,
    `operation` STRING,
    `window_start` TIMESTAMP(3),
    `window_end` TIMESTAMP(3),
    `update_count` BIGINT,
    `http_status_code` INT  -- Field to capture the HTTP response code
) WITH (
    'connector' = 'http-sink',
    'url' = 'http://rest-simulator:5000/v1/member/update',
	--'topic' = 'oracle_api_sink',
    --'method' = 'POST',
    'format' = 'json'
	--'headers' = '{ "Content-Type": "application/json" }'  // Adjust headers as needed
);

INSERT INTO oracle_api_sink
SELECT 
    request_id,
    payload,
    operation,
    window_start,
    window_end,
    update_count,
	http_status_code
FROM oracle_banking_payload;


INSERT INTO error_queue
SELECT 
    request_id,
    'API call failed with non-200 status code' AS error_message,
    payload,
    operation,
    window_start,
    window_end
    http_status_code
FROM oracle_api_sink
WHERE http_status_code <> 200;

CREATE TABLE kafka_debug_table (
    `request_id` STRING,
    `payload` STRING,
    `operation` STRING,
    `window_start` TIMESTAMP(3),
    `window_end` TIMESTAMP(3),
    `update_count` BIGINT
) WITH (
    'connector' = 'kafka',
    'topic' = 'debug_topic',
	'scan.startup.mode' = 'earliest-offset',
    'properties.bootstrap.servers' = 'broker:9094',
	'properties.group.id' = 'flink_debug_group',
    'format' = 'json'
);
