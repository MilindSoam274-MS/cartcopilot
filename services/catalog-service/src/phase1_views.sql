create or replace view phase1_restaurants as
select *
from restaurants
where city in ('Bangalore','Delhi','Mumbai');

create or replace view phase1_menu_items as
select *
from menu_items
where city in ('Bangalore','Delhi','Mumbai');