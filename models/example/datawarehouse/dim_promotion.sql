WITH source AS (

    SELECT

        promotion_id,
        discount,

        current_localtimestamp() AS insertion_timestamp

    FROM {{ ref('stg_promotions') }}

),

unique_source AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY promotion_id
        ) AS row_num

    FROM source

)

SELECT *

EXCLUDE (row_num)

FROM unique_source

WHERE row_num = 1