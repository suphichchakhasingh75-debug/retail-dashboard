{{ config(

    partition_by = {
        "field": "order_date",
        "data_type": "date"
    }

) }}

WITH source AS (

    SELECT
        oi.order_id,
        oi.product_id,

        o.customer_id,
        o.store_id,
        o.promotion_id,

        p.supplier_id,

        pay.payment_id,

        oi.qty AS quantity,
        oi.price,

        promo.discount,

        CAST(o.order_date AS DATE) AS order_date,

        oi.qty * oi.price AS sale_amount

    FROM {{ ref('stg_orders') }} AS o

    LEFT JOIN {{ ref('stg_order_items') }} AS oi
        ON oi.order_id = o.order_id

    LEFT JOIN {{ ref('stg_products') }} AS p
        ON oi.product_id = p.product_id

    LEFT JOIN {{ ref('stg_promotions') }} AS promo
        ON o.promotion_id = promo.promotion_id

    LEFT JOIN {{ ref('stg_payments') }} AS pay
        ON o.order_id = pay.order_id

    WHERE oi.order_id IS NOT NULL

),

unique_source AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY
                order_id,
                product_id,
                customer_id,
                store_id,
                promotion_id,
                order_date
        ) AS row_number

    FROM source

)

SELECT

    order_id,
    product_id,
    order_date,
    customer_id,
    store_id,
    promotion_id,
    supplier_id,
    payment_id,

    quantity,
    price,
    discount,
    sale_amount

FROM unique_source

WHERE row_number = 1