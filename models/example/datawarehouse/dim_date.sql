WITH source AS (

    SELECT DISTINCT

        CAST(order_date AS DATE) AS order_date

    FROM {{ ref('stg_orders') }}

    WHERE order_date IS NOT NULL

),

unique_source AS (

    SELECT

        CAST(
            STRFTIME(order_date, '%Y%m%d')
            AS INTEGER
        ) AS date_id,

        order_date,

        EXTRACT(DAY FROM order_date) AS day,

        EXTRACT(MONTH FROM order_date) AS month,

        EXTRACT(QUARTER FROM order_date) AS quarter,

        EXTRACT(YEAR FROM order_date) AS year,

        current_localtimestamp() AS insertion_timestamp

    FROM source

)

SELECT *

FROM unique_source