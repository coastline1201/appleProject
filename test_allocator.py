import csv
import allocator
import os
import pytest

allocator.FILE_PATH = 'testdata/'

SOURCING_FILE = [
    ['site','customer','product'],
    ['1206','C001','P001'],
    ['1203','C001','P001'],
    ['1206','C002','P001'],
    ['1203','C002','P001'],
    ['1206','C003','P001'],
    ['1203','C004','P001'],
    ['1206','C001','P002'],
    ['1206','C002','P002'],
]

SUPPLY_FILE = [
    ['site','product','date','quantity'],
    ['1206','P001','1/7/19','2000'],
    ['1206','P001','2/7/19','1000'],
    ['1206','P001','3/7/19','1000'],
    ['1206','P001','4/7/19','1000'],
    ['1206','P001','5/7/19','0'],
    ['1206','P001','6/7/19','0'],
    ['1203','P001','1/7/19','2000'],
    ['1203','P001','2/7/19','1000'],
    ['1203','P001','3/7/19','0'],
    ['1203','P001','4/7/19','1000'],
    ['1203','P001','5/7/19','0'],
    ['1203','P001','6/7/19','1000'],
    ['1206','P002','1/7/19','1000'],
    ['1206','P002','2/7/19','2000'],
    ['1206','P002','3/7/19','0'],
    ['1206','P002','4/7/19','500'],
    ['1206','P002','5/7/19','2000'],
    ['1206','P002','6/7/19','1000'],
]

def setup_module():
    os.mkdir('testdata')


def teardown_module():
    os.remove('testdata/order_file.csv')
    os.remove('testdata/supply_file.csv')
    os.remove('testdata/sourcing_file.csv')
    os.rmdir('testdata')


def test_over_supply():
    order_file = [
        ['customer','product','date','quantity'],
        ['C001','P001','1-Jul-19','5000'],
        ['C001','P002','5-Jul-19','200'],
        ['C002','P001','3-Jul-19','550'],
        ['C002','P002','7-Jul-19','300'],
    ]
    expected = [
        ['site', 'customer', 'product', '2019-07-01', '2019-07-02'],
        ['1203', 'C001', 'P001', '2000', '1000'],
        ['1206', 'C001', 'P001', '2000', ''],
        ['1206', 'C002', 'P001', '', '550'],
        ['1206', 'C001', 'P002', '200', ''],
        ['1206', 'C002', 'P002', '300', ''],
    ]
    assert allocate(order_file) == expected

def test_over_demand():
    order_file = [
        ['customer','product','date','quantity'],
        ['C001','P001','1-Jul-19','20000'],
        ['C002','P001','5-Jul-19','5000'],
    ]
    expected = [
        ['site', 'customer', 'product', '2019-07-01', '2019-07-02', '2019-07-03', '2019-07-04', '2019-07-06'],
        ['1203', 'C001', 'P001', '2000', '1000', '', '1000', '1000'],
        ['1206', 'C001', 'P001', '2000', '1000', '1000', '1000', ''],
    ]
    assert allocate(order_file) == expected

def test_unbalanced_sourcing_site():
    order_file = [
        ['customer','product','date','quantity'],
        ['C001','P001','1-Jul-19','5000'],
        ['C003','P001','2-Jul-19','5000'],
    ]
    expected = [
        ['site', 'customer', 'product', '2019-07-01', '2019-07-02', '2019-07-03', '2019-07-04'],
        ['1203', 'C001', 'P001', '2000', '1000', '', ''],
        ['1206', 'C001', 'P001', '2000', '', '', ''],
        ['1206', 'C003', 'P001', '', '1000', '1000', '1000',],
    ]
    assert allocate(order_file) == expected

def test_order_on_dame_day():
    order_file = [
        ['customer','product','date','quantity'],
        ['C001','P001','1-Jul-19','3000'],
        ['C002','P001','1-Jul-19','500'],
        ['C001','P001','2-Jul-19','3000'],
        ['C002','P001','2-Jul-19','500'],
        ['C001','P002','1-Jul-19','2000'],
        ['C002','P002','1-Jul-19','3000'],
    ]
    expected = [
        ['site', 'customer', 'product', '2019-07-01', '2019-07-02', '2019-07-03', '2019-07-04', '2019-07-05'],
        ['1203', 'C001', 'P001', '1714', '', '', '', ''],
        ['1206', 'C001', 'P001', '1286', '', '', '', ''],
        ['1203', 'C002', 'P001', '286', '', '', '', ''],
        ['1206', 'C002', 'P001', '214', '', '', '', ''],
        ['1206', 'C001', 'P002', '400', '800', '', '200', '600'],
        ['1206', 'C002', 'P002', '600', '1200', '', '300', '900'],
        ['1203', 'C001', 'P001', '', '857', '', '1', ''],
        ['1206', 'C001', 'P001', '428', '857', '857', '', ''],
        ['1203', 'C002', 'P001', '', '143', '', '', ''],
        ['1206', 'C002', 'P001', '72', '143', '142', '', ''],
    ]
    assert allocate(order_file) == expected

# customer order with fewer sourcing sites has less demand,
# site providing for more customers are sorted after the other site
def test_order_on_dame_day_w_unbalanced_sourcing_site_1():
    order_file = [
        ['customer','product','date','quantity'],
        ['C001','P001','1-Jul-19','3000'],
        ['C002','P001','1-Jul-19','2000'],
        ['C003','P001','1-Jul-19','500'],
    ]
    expected = [
        ['site', 'customer', 'product', '2019-07-01', '2019-07-02'],
        ['1203', 'C001', 'P001', '1200', '600'],
        ['1206', 'C001', 'P001', '1090', '110'],
        ['1203', 'C002', 'P001', '800', '400'],
        ['1206', 'C002', 'P001', '727', '73'],
        ['1206', 'C003', 'P001', '183', '317'],
    ]
    assert allocate(order_file) == expected

# customer order with fewer sourcing sites has more demand
# site providing for more customers are sorted after the other site
def test_order_on_dame_day_w_unbalanced_sourcing_site_2():
    order_file = [
        ['customer','product','date','quantity'],
        ['C001','P001','1-Jul-19','500'],
        ['C002','P001','1-Jul-19','600'],
        ['C003','P001','1-Jul-19','3000'],
    ]
    expected = [
        ['site', 'customer', 'product', '2019-07-01', '2019-07-02'],
        ['1203', 'C001', 'P001', '500', ''],
        ['1203', 'C002', 'P001', '600', ''],
        ['1206', 'C003', 'P001', '2000', '1000'],
    ]
    assert allocate(order_file) == expected

# customer order with fewer sourcing sites has less demand
# site providing for more customers are sorted before the other site
def test_order_on_dame_day_w_unbalanced_sourcing_site_3():
    order_file = [
        ['customer','product','date','quantity'],
        ['C001','P001','1-Jul-19','3000'],
        ['C002','P001','1-Jul-19','2000'],
        ['C004','P001','1-Jul-19','500'],
    ]
    expected = [
        ['site', 'customer', 'product', '2019-07-01', '2019-07-02', '2019-07-04'],
        ['1203', 'C001', 'P001', '1090', '545', ''],
        ['1206', 'C001', 'P001', '1200', '165', ''],
        ['1203', 'C002', 'P001', '727', '363', ''],
        ['1206', 'C002', 'P001', '800', '110', ''],
        ['1203', 'C004', 'P001', '183', '92', '225']
    ]
    assert allocate(order_file) == expected

# customer order with fewer sourcing sites has more demand
# site providing for more customers are sorted before the other site
def test_order_on_dame_day_w_unbalanced_sourcing_site_4():
    order_file = [
        ['customer','product','date','quantity'],
        ['C001','P001','1-Jul-19','500'],
        ['C002','P001','1-Jul-19','600'],
        ['C004','P001','1-Jul-19','3000'],
    ]
    expected = [
        ['site', 'customer', 'product', '2019-07-01', '2019-07-02', '2019-07-04'],
        ['1203', 'C001', 'P001', '243', '', ''],
        ['1206', 'C001', 'P001', '257', '', ''],
        ['1203', 'C002', 'P001', '292', '', ''],
        ['1206', 'C002', 'P001', '308', '', ''],
        ['1203', 'C004', 'P001', '1465', '1000', '535']
    ]
    assert allocate(order_file) == expected

def test_empty_order():
    order_file = [
        ['customer','product','date','quantity']
    ]
    assert allocate(order_file) == [['site', 'customer', 'product']]
    order_file.append(['C001','P001','1-Jul-19','0'])
    assert allocate(order_file) == [['site', 'customer', 'product']]

def test_empty_supply():
    order_file = [
        ['customer','product','date','quantity'],
        ['C001','P001','1-Jul-19','2000'],
    ]
    supply_file = [
        ['site','product','date','quantity']
    ]
    assert allocate(order_file, supply_file=supply_file) == [['site', 'customer', 'product']]
    supply_file.append(['1206','P001','1/7/19','0'])
    assert allocate(order_file, supply_file=supply_file) == [['site', 'customer', 'product']]

def test_empty_sourcing():
    order_file = [
        ['customer','product','date','quantity'],
        ['C001','P001','1-Jul-19','2000'],
    ]
    sourcing_file = [
        ['site','customer','product']
    ]
    assert allocate(order_file, sourcing_file=sourcing_file) == [['site', 'customer', 'product']]

def allocate(order_file, supply_file = SUPPLY_FILE, sourcing_file = SOURCING_FILE):
    # write to test directory
    with open(allocator.FILE_PATH + 'order_file.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for row in order_file:
            writer.writerow(row)
    with open(allocator.FILE_PATH + 'sourcing_file.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for row in sourcing_file:
            writer.writerow(row)
    with open(allocator.FILE_PATH + 'supply_file.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for row in supply_file:
            writer.writerow(row)
    # perform allocation
    orders = allocator.readOrderFile()
    sourcing_map = allocator.readSourcingFile()
    supply_map = allocator.readSupplyFile()
    return allocator.allocate(orders, sourcing_map, supply_map)