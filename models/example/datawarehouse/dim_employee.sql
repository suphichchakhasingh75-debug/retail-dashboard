WITH source AS (

    SELECT

        employee_id,
        store_id,
        salary,

        current_localtimestamp() AS insertion_timestamp

    FROM {{ ref('stg_employees') }}

),

unique_source AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY employee_id
        ) AS row_num

    FROM source

)

SELECT *

EXCLUDE (row_num)

FROM unique_source

WHERE row_num = 1