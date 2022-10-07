import csv
import re
import threading
import requests
from contextlib import suppress
from multiprocessing.dummy import Pool as ThreadPool
from typing import Any, Dict, Optional

# from fp.fp import FreeProxy

# Synchronization object used to lock output file
threadlock = threading.Lock()

# Number of 'sumultaneous' threads
NUM_THREADS: int = 4

# Calculate item rarity based on CSS class
RARITY: Dict[int, str] = {
    0: 'poor',
    1: 'common',
    2: 'uncommon',
    3: 'rare',
    4: 'epic',
    5: 'legendary',
    6: 'artifact'
}

ids = []
not_found_ids = []

# Marker of non-existent item
NOT_FOUND = 'It may have been removed from the game.'

# Regex constants for obtaining values
RE_NAME = r'!--nstart--><b class=\\"q\d{1}\\">([a-zA-Z0-9 \':\-,().]*)'
RE_ITEMLEVEL = r'<!--ilvl-->(\d*)<'
RE_BINDS = r'bo--><br>([a-zA-Z_ ]*)'
RE_RARITY = r'<!--nstart--><b class=\\"q(\d{1})'
RE_UNIQUE = r'bo--><br>[a-zA-Z0-9_ ]*<br>([a-zA-Z]*)'
RE_MIN_DMG = r'dmg-->(\d+)'
RE_MAX_DMG = r'dmg-->\d+ - (\d+)'
RE_DPS = r'<!--dps-->\(([0-9.]*)'
RE_SPEED = r'<!--spd-->([\d.]*)'
RE_EQUIP_SLOT = r'<table width=\\"100%\\"><tr><td>([a-zA-Z- ]*)'
RE_TYPE = r'<span class=\\"q1\\">([a-zA-Z-]*)'
RE_DURABILITY = r'<!--ps--><br>[a-zA-Z ]*([0-9]*)'
RE_MOUNT = r'ue--><br.*\/>([a-zA-Z0-9 ]*)'
RE_REQUIRES_LEVEL = r'<!--rlvl-->([0-9]*)'
RE_ARMOR = r'<!--amr-->([\d]*) Armor'
RE_BLOCK = r'<br>([\d]*) Block<'
RE_STAMINA = r'stat\d-->([-+\d]*) Stamina'
RE_STRENGTH = r'stat\d-->([-+\d]*) Strength'
RE_AGILITY = r'stat\d-->([-+\d]*) Agility'
RE_INTELLECT = r'stat\d-->([-+\d]*) Intellect'
RE_SPIRIT = r'stat\d-->([-+\d]*) Spirit'
RE_FIRE_RES = r'>([0-9+]*) Fire Resistance<'
RE_SHADOW_RES = r'>([0-9+]*) Shadow Resistance<'
RE_NATURE_RES = r'>([0-9+]*) Nature Resistance<'
RE_FROST_RES = r'>([0-9+]*) Frost Resistance<'
RE_ARCANE_RES = r'>([0-9+]*) Arcane Resistance<'
RE_EFFECTS = r'" class=\\"q2\\">([a-zA-Z0-9 %.&;]*)'
RE_ELIGIBLE_CLASSES = r'" class=\\"c[\d]*\\">([a-zA-Z]*)'
RE_SET_NAME = r'item-set.*class=\\"q\\">([a-zA-Z\' ]*)'
RE_RANDOM_ENCHANTMENT = r'<span class=\\"q2\\">&lt;([a-zA-Z0-9 ]*)'
RE_REQUIRE_PROFESSION = r'Requires .*">([A-Za-z ]*)<\\/a> \(([\d]*)\)'
RE_BEGINS_A_QUEST = r'(This Item Begins a Quest)'
RE_FLAVOUR_TEXT = r'<span class=\\"q\\">&quot;([a-zA-Z- !\']*)&quot;'
RE_GOLD = r'<span class=\\"moneygold\\">([\d]*)'
RE_SILVER = r'<span class=\\"moneysilver\\">([\d]*)'
RE_COPPER = r'<span class=\\"moneycopper\\">([\d]*)'
RE_NOT_AVAILABLE_TO_PLAYERS = r'(This item is not available to players.)<\/b>'
RE_DEPRECATED = r'class=tip](Deprecated)\[\\\/span'


# List of fields for CSV file
fields = [
    'id',                   # Id of the item on classic.wowhead.com
    'name',                 # Name of the item
    'item level',           # Item Level
    'rarity',               # poor, common, uncommon, rare, epic, or legendary
    'binds',                # Binds on equip / pickup, Binds when used, or None
    'unique',               # Is this item unique or not
    'min dmg',              # Min dmg (weapon only)
    'max dmg',              # Max dmg (weapon only)
    'speed',                # Speed of a weapon
    'dps',                  # Damage per second (weapon only)
    'equip slot',           # Two-Hand, One Hand, etc
    'type',                 # Sword, Mace, etc
    'stamina',              # ^
    'intellect',            # |
    'agility',              # Primary stats
    'spirit',               # (STA, INT, AGI, SPI, STR, ARMOR, BLOCK)
    'strength',             # |
    'armor',                # |
    'block',                # v
    'fire res',             # ^
    'nature res',           # Resistances on item
    'frost res',            # (fire, nature, frost, shadow, arcane)
    'shadow res',           # |
    'arcane res',           # v
    'durability',           # Durability of the item
    'requires level',       # Level requirement for this item
    'effects',              # Various effects applied on this item
    'sell price',           # Sell price of the item
    'set',                  # Name of set if this item is a part of the set
    'class',                # Classes eligible for this item
    'enchantment',          # Sometimes item have random enchantment
    'flavour text',         # Text in quotes not related to game mechanics
    'requires profession',  # Profession requirements
    'begins quest',         # This item begins a quest
    'dropped by',           # Monsters names that can drop this item on death
    'n/a to players',       # This item is not available to players
    'deprecated'            # This item has deprecated flag
    ]


def mark_id(id: int) -> None:
    s_id = str(id)
    if s_id in not_found_ids:
        print(f'Not found: {s_id} is in list')
        return

    not_found_ids.append(s_id)
    with open('not_found', 'a') as f:
        f.write(f'{s_id}\n')


def get_page_body(id: int) -> str:
    """Make request, fetch data, and write it to CSV file if item exists"""
    print(f'{threading.get_ident()} id {str(id)} .... ', end='')

    url = f'https://classic.wowhead.com/item={id}'
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.101 Safari/537.36'}
    # proxy = FreeProxy(rand=True).get()
    # body = requests.get(url, headers=headers, proxies={'http': proxy}).text
    body = requests.get(url, headers=headers).text

    # If item is not found, mark id as done and move on
    if NOT_FOUND in body:
        print('Not found')

        mark_id(id)
        return ''

    return body


def fill_dictionary(id: int, r: str) -> Dict[str, Optional[Any]]:
    """Make request, fetch data, and write it to CSV file if item exists"""
    # A dictionary object to write to CSV file
    d = dict.fromkeys(fields)

    # Uncomment to create dump file for an item in working directory
    # with open(f'id{id}.html', 'wb') as output_file:
    #     output_file.write(r.encode('utf8'))

    d['id'] = id
    d['name'] = re.findall(RE_NAME, r)[0]
    d['item level'] = re.findall(RE_ITEMLEVEL, r)[0]
    d['rarity'] = RARITY[int(re.findall(RE_RARITY, r)[0])]

    with suppress(IndexError):
        d['binds'] = re.findall(RE_BINDS, r)[0]

    with suppress(IndexError):
        d['unique'] = re.findall(RE_UNIQUE, r)[0]

    with suppress(IndexError):
        d['min dmg'] = re.findall(RE_MIN_DMG, r)[0]
        d['max dmg'] = re.findall(RE_MAX_DMG, r)[0]
        d['dps'] = re.findall(RE_DPS, r)[0]
        d['speed'] = re.findall(RE_SPEED, r)[0]

    with suppress(IndexError):
        d['equip slot'] = re.findall(RE_EQUIP_SLOT, r)[0]
    with suppress(IndexError):
        d['type'] = re.findall(RE_TYPE, r)[0]
    with suppress(IndexError):
        d['durability'] = re.findall(RE_DURABILITY, r)[0]
    with suppress(IndexError):
        # If this is a mount, overwrite its type
        d['type'] = re.findall(RE_MOUNT, r)[0]
    with suppress(IndexError):
        d['requires level'] = re.findall(RE_REQUIRES_LEVEL, r)[0]
    with suppress(IndexError):
        d['armor'] = re.findall(RE_ARMOR, r)[0]
    with suppress(IndexError):
        d['block'] = re.findall(RE_BLOCK, r)[0]

    # Primary stats
    with suppress(IndexError):
        d['stamina'] = re.findall(RE_STAMINA, r)[0]
    with suppress(IndexError):
        d['agility'] = re.findall(RE_AGILITY, r)[0]
    with suppress(IndexError):
        d['intellect'] = re.findall(RE_INTELLECT, r)[0]
    with suppress(IndexError):
        d['strength'] = re.findall(RE_STRENGTH, r)[0]
    with suppress(IndexError):
        d['spirit'] = re.findall(RE_SPIRIT, r)[0]

    # Resistances
    with suppress(IndexError):
        d['fire res'] = re.findall(RE_FIRE_RES, r)[0]
    with suppress(IndexError):
        d['shadow res'] = re.findall(RE_SHADOW_RES, r)[0]
    with suppress(IndexError):
        d['nature res'] = re.findall(RE_NATURE_RES, r)[0]
    with suppress(IndexError):
        d['frost res'] = re.findall(RE_FROST_RES, r)[0]
    with suppress(IndexError):
        d['arcane res'] = re.findall(RE_ARCANE_RES, r)[0]

    effects_list = re.findall(RE_EFFECTS, r)
    if len(effects_list) > 0:
        d['effects'] = ', '.join(effects_list).replace('&nbsp;', '')

    classes_list = re.findall(RE_ELIGIBLE_CLASSES, r)
    if len(classes_list) > 0:
        d['class'] = ', '.join(classes_list)

    sell_price = ''
    gold_list = re.findall(RE_GOLD, r)
    if len(gold_list) > 0:
        sell_price += f'{gold_list[0]}g '
    silver_list = re.findall(RE_SILVER, r)
    if len(silver_list) > 0:
        sell_price += f'{silver_list[0]}s '
    copper_list = re.findall(RE_COPPER, r)
    if len(copper_list) > 0:
        sell_price += f'{copper_list[0]}c'
    d['sell price'] = sell_price

    with suppress(IndexError):
        d['set'] = re.findall(RE_SET_NAME, r)[0]

    with suppress(IndexError):
        d['enchantment'] = re.findall(RE_RANDOM_ENCHANTMENT, r)[0]

    other_requirements_list = re.findall(RE_REQUIRE_PROFESSION, r)
    if len(other_requirements_list) > 0:
        d['requires profession'] = ':'.join(map(str, other_requirements_list))

    with suppress(IndexError):
        d['begins quest'] = re.findall(RE_BEGINS_A_QUEST, r)[0]

    dropped_by_list = re.findall("\"name\":\"([a-zA-Z ']*)\",\"react\"", r)
    if len(dropped_by_list) > 0:
        d['dropped by'] = ', '.join(dropped_by_list)

    with suppress(IndexError):
        d['flavour text'] = re.findall(RE_FLAVOUR_TEXT, r)[0]

    with suppress(IndexError):
        d['n/a to players'] = re.findall(RE_NOT_AVAILABLE_TO_PLAYERS, r)[0]

    with suppress(IndexError):
        d['deprecated'] = re.findall(RE_DEPRECATED, r)[0]

    return d


def add_to_file(d: Dict) -> None:
    """Add current item to CSV file"""
    # Dictionary object is ready to write. Open CSV file in 'append' mode
    with threadlock:
        with open('names.csv', 'a', newline='') as csvfile:
            fieldnames = fields
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            # Uncomment to write header before every line
            # writer.writeheader()
            writer.writerow(d)

    print(d['name'])


def do(id: int):
    """Основная функция, которую можно засунуть в много потоков."""
    item_page_body = get_page_body(id)       # Get item page source
    if item_page_body == '':                 # Nothing was found
        return                               # Continue with next id

    d = fill_dictionary(id, item_page_body)  # Parse page into dictionary
    add_to_file(d)                           # Write dictionary to file


if __name__ == '__main__':
    with open('not_found', 'r') as f:
        not_found_ids = f.read().splitlines()
    # create list of ids 50000
    ids = [str(x) for x in range(50000)]
    ids = list(set(ids).difference(not_found_ids))

    print('total excluding not found: ', len(ids))

    # Calculate not processed ids
    with open('names.csv', 'r') as f:
        processed_ids = f.read().splitlines()
        
        # No duplicates are allowed in resulting file
        assert len(processed_ids) == len(set(processed_ids))
        lines = f.readlines()
        for line in lines:
            cur_id = re.findall(r'^([\d]*)', line)[0]
            if len(cur_id) != 0 and cur_id.isdigit() and cur_id in ids:
                ids.remove(cur_id)
    print('to process: ', len(ids))

    with ThreadPool(NUM_THREADS) as p: p.map(do, ids)
