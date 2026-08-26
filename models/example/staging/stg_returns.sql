with source as (

    select * from {{source('retail_data','returns')}}
)
select
    *,
    current_localtimestamp() as ingestion_timestamp
from source