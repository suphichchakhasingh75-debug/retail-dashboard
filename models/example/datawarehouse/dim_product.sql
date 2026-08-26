WITH source AS (

    SELECT

        product_id,
        category_id,
        supplier_id,
        price,

        current_localtimestamp() AS insertion_timestamp

    FROM {{ ref('stg_products') }}

),

unique_source AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY product_id
        ) AS row_num

    FROM source

)

SELECT *

EXCLUDE (row_num)

FROM unique_source

WHERE row_num = 1