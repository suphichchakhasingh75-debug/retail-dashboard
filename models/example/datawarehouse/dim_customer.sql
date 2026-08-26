WITH source AS (

    SELECT

        customer_id,
        city,
        signup_date,

        current_localtimestamp() AS insertion_timestamp

    FROM {{ ref('stg_customers') }}

),

unique_source AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
        ) AS row_num

    FROM source

)

SELECT *

EXCLUDE (row_num)

FROM unique_source

WHERE row_num = 1