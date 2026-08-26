with source as (

    select * from {{source('retail_data','promotions')}}
)
select
    *,
    current_localtimestamp() as ingestion_timestamp
from source