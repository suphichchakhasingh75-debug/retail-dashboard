with source as (

    select * from {{source('retail_data','order_items')}}
)
select
    *,
    current_localtimestamp() as ingestion_timestamp
from source