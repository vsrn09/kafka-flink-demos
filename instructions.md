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




CREATE TABLE createRmMember_Flink (
    `member` ROW< 
        `backupWithholdingCode` STRING,
        `branchOfService` STRING,
        `currencyCode` STRING,
        `easodt` STRING,
        `employment` ROW< 
            `annualIncome` STRING,
            `contactHistory` ROW< 
                `emailAddresses` ARRAY<ROW<`emailAddress` STRING>>,
                `phoneNumbers` ARRAY<ROW<`phoneNumber` STRING>>,
                `postalAddresses` ARRAY<ROW<`addressLine1` STRING, `city` STRING, `state` STRING, `zipCode` STRING, `countryCode` STRING>>
            >,
            `employerName` STRING,
            `employmentEndDate` STRING,
            `employmentStartDate` STRING,
            `jobTitle` STRING,
            `occupation` STRING
        >,
        `empStatus` STRING,
        `issuedIdentifications` ARRAY<ROW<`idDescription` STRING, `idNumber` STRING, `idType` STRING>>,
        `language` STRING,
        `lastContactDate` STRING,
        `membershipStatus` STRING,
        `membershipSubType` STRING,
        `membershipType` STRING,
        `personData` ROW< 
            `bankRegion` STRING,
            `dateOfBirth` STRING,
            `fullName` STRING,
            `gender` STRING,
            `givenName` STRING,
            `familyName` STRING,
            `prefix` STRING
        >,
        `preferredBank` STRING,
        `relationshipManagers` ARRAY<ROW<`relationshipId` STRING, `relationshipRole` STRING>>
    >,
    `NECURARequestHeader` ROW<`consumerChannel` STRING, `consumingApplicationName` STRING, `credential` STRING, `rqUID` STRING>,
    `lastUpdateDate` TIMESTAMP(3),
    `event_time` AS `lastUpdateDate`,  -- Directly use the timestamp field
    WATERMARK FOR `event_time` AS `event_time` - INTERVAL '1' SECOND -- Reduced watermark delay
) WITH (
    'connector' = 'kafka',
    'topic' = 'createRmMember',
    'properties.bootstrap.servers' = 'broker:9094',
	'properties.group.id' = 'flink_create_member_grp',
	--'key.fields' = 'member_id',
	'properties.request.timeout.ms' = '60000',
	'properties.retry.backoff.ms' = '1000',
    --'key.format' = 'raw',
    'format' = 'json',
    'scan.startup.mode' = 'earliest-offset'
);

CREATE TABLE transformRmMemberCreate_Flink (
    `applicationNumber` STRING,
    `applicationPriority` STRING,
    `businessProductCode` STRING,
    `cmcReplicationReq` BOOLEAN,
    `hostHandoffReq` BOOLEAN,
    `kycReferenceNumber` STRING,
    `notificationReq` BOOLEAN,
    `partyType` STRING,
    `retailPartyModel` ARRAY<ROW< 
        `basicInfoAndCitizenshipDetails` ROW<
            `applicationNumber` STRING,
            `countryOfResidence` STRING,
            `dateOfBirth` STRING,
            `firstName` STRING,
            `isCustomer` BOOLEAN,
            `language` STRING,
            `lastName` STRING,
            `nationality` STRING,
            `partySubType` STRING,
            `partyType` STRING,
            `residencyStatus` STRING,
            `title` STRING
        >,
        `contactDetails` ROW<
            `partyContactDetailsList` ARRAY<ROW<
                `line1` STRING,
                `mediaType` STRING,
                `preferred` BOOLEAN
            >>
        >,
        `currentAddressDetails` ROW<
            `partyContactDetailsList` ARRAY<ROW<
                `addressFrom` STRING,
                `addressType` STRING,
                `buildingName` STRING,
                `city` STRING,
                `country` STRING,
                `currentAddress` BOOLEAN,
                `location` STRING,
                `preferred` BOOLEAN,
                `state` STRING,
                `streetName` STRING,
                `zipCode` STRING
            >>
        >,
        `externalRefNo` STRING,
        `idDetails` ROW<
            `partyIdInfoDetailsList` ARRAY<ROW<
                `idStatus` STRING,
                `idType` STRING,
                `placeOfIssue` STRING,
                `preferred` BOOLEAN,
                `remarks` STRING,
                `uniqueId` STRING,
                `validFrom` STRING,
                `validTill` STRING
            >>
        >,
        `taxDeclarationDetails` ROW<
            `asOnDate` STRING,
            `partyTaxInfoDetailsList` ARRAY<ROW<
                `formType` STRING,
                `remarks` STRING,
                `validFrom` STRING
            >>
        >
    >>,
    `sourceProductId` STRING,
    `validationReq` BOOLEAN
) WITH (
    'connector' = 'kafka',
    'topic' = 'transformRmMemberCreate',
    'properties.bootstrap.servers' = 'broker:9094',
    'properties.group.id' = 'flink_transform_create_member_grp',
	'properties.request.timeout.ms' = '60000',
	'properties.retry.backoff.ms' = '1000',
    'format' = 'json',
	'scan.startup.mode' = 'earliest-offset'
);



INSERT INTO transformRmMemberCreate_Flink
SELECT 
    mi.applicationNumber,
    'Normal' AS applicationPriority,
    'REOB' AS businessProductCode,
    TRUE AS cmcReplicationReq,
    FALSE AS hostHandoffReq,
    'string' AS kycReferenceNumber,
    TRUE AS notificationReq,
    'I' AS partyType,
    ARRAY[
        ROW(
            ROW(
                mi.applicationNumber,
                'US',
                mi.member.personData.dateOfBirth,
                mi.member.personData.givenName,
                TRUE,
                mi.member.language,
                mi.member.personData.familyName,
                'US',
                'INDIVIDUAL',
                'I',
                'C',
                mi.member.personData.prefix
            ),
            ROW(
                ARRAY[
                    ROW(
                        mi.member.personData.contactHistory.emailAddresses[1].emailAddress,
                        'EML',
                        TRUE
                    ),
                    ROW(
                        mi.member.personData.contactHistory.phoneNumbers[1].phoneNumber,
                        'MBL',
                        TRUE
                    )
                ]
            ),
            ROW(
                ARRAY[
                    ROW(
                        '2015-01-30',
                        'C',
                        mi.member.employment.contactHistory.postalAddresses[1].addressLine1,
                        mi.member.employment.contactHistory.postalAddresses[1].city,
                        mi.member.employment.contactHistory.postalAddresses[1].countryCode,
                        TRUE,
                        'US',
                        TRUE,
                        mi.member.employment.contactHistory.postalAddresses[1].state,
                        mi.member.employment.contactHistory.postalAddresses[1].addressLine2,
                        mi.member.employment.contactHistory.postalAddresses[1].zipCode
                    )
                ]
            ),
            '00000000145999' AS externalRefNo,
            ROW(
                ARRAY[
                    ROW(
                        'AVL',
                        'PPT',
                        'LA',
                        TRUE,
                        'ID card is valid',
                        'A234',
                        '2002-01-30',
                        '2031-01-30'
                    )
                ]
            ),
            ROW(
                '2022-03-12',
                ARRAY[
                    ROW(
                        'W9',
                        'tax compliant',
                        '2024-10-30'
                    )
                ]
            )
        )
    ] AS retailPartyModel,
    'OBPY' AS sourceProductId,
    FALSE AS validationReq
FROM createRmMember_Flink AS mi
WINDOW HOP (`event_time`, INTERVAL '1' SECOND, INTERVAL '1' SECOND) -- Sliding window with 1 second interval
GROUP BY 
    mi.applicationNumber,
    mi.member.personData.dateOfBirth,
    mi.member.personData.givenName,
    mi.member.language,
    mi.member.personData.familyName,
    mi.member.personData.prefix,
    mi.member.personData.contactHistory.emailAddresses[1].emailAddress,
    mi.member.personData.contactHistory.phoneNumbers[1].phoneNumber,
    mi.member.employment.contactHistory.postalAddresses[1].addressLine1,
    mi.member.employment.contactHistory.postalAddresses[1].city,
    mi.member.employment.contactHistory.postalAddresses[1].countryCode,
    mi.member.employment.contactHistory.postalAddresses[1].state,
    mi.member.employment.contactHistory.postalAddresses[1].addressLine2,
    mi.member.employment.contactHistory.postalAddresses[1].zipCode,
    mi.member.language;
