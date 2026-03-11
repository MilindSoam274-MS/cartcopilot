--City remapping table (for synthetic multi-city behaviour)

Create table if not exists city_map (
    source_city text primary key,
    mapped_city text not null,
    active boolean not null default TRUE
);

-- Restaurants table (one row per restaurant per mapped city)
Create table if not exists restaurants(
    restaurant_id BIGINT primary key,
    city text not null,
    subcity text,
    name text not null,
    cuisine Text,
    rating text,
    rating_count text,
    cost_for_two text,
    address text
);

-- Menu items table (one row per menu item)
create table if not exists menu_items(
    item_id text primary key,
    restaurant_id bigint not null references restaurants(restaurant_id),
    city text not null,
    category text,
    item_name text not null,
    price numeric,
    veg_flag text,
    cuisine text,
    embedding_text text not null
);

create index if not exists idx_menu_items_city ON menu_items(city);
create index if not exists idx_menu_items_restaurant on menu_items(restaurant_id);
create index if not exists idx_menu_items_category on menu_items(category);
create index if not exists idx_menu_items_vegflag on menu_items(veg_flag);