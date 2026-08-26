WITH source AS (

    SELECT

        payment_id,
        order_id,
        amount,

        current_localtimestamp() AS insertion_timestamp

    FROM {{ ref('stg_payments') }}

),

unique_source AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY payment_id
        ) AS row_num

    FROM source

)

SELECT *

EXCLUDE (row_num)

FROM unique_source

WHERE row_num = 1