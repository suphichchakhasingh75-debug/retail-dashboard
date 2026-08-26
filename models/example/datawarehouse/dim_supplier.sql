WITH source AS (

    SELECT

        supplier_id,
        country,

        current_localtimestamp() AS insertion_timestamp

    FROM {{ ref('stg_suppliers') }}

),

unique_source AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY supplier_id
        ) AS row_num

    FROM source

)

SELECT *

EXCLUDE (row_num)

FROM unique_source

WHERE row_num = 1