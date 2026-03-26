import sqlite3
from datetime import datetime, timedelta
import random

conn = sqlite3.connect('delivery_service.db')
cursor = conn.cursor()


cursor.execute('''
    SELECT к.транспорт, COUNT(*) as количество
    FROM заказы з
    JOIN курьеры к ON з.курьер_id = к.id
    WHERE з.статус = 'delivered' 
    AND strftime('%Y', з.дата_доставки) = strftime('%Y', 'now')
    GROUP BY к.транспорт
    ORDER BY количество DESC
    LIMIT 1;
''')
result = cursor.fetchone()
print("\n1. Каким способом (транспортом) было доставлено больше заказов в этом году:")
if result:
    print(f"   {result[0]} - {result[1]} заказов")
else:
    print("   Нет доставленных заказов в этом году")


cursor.execute('''
    SELECT к.имя || ' ' || к.фамилия as клиент, SUM(з.сумма) as общая_сумма
    FROM клиенты к
    JOIN заказы з ON к.id = з.клиент_id
    WHERE з.статус != 'cancelled'
    AND strftime('%Y-%m', з.дата_заказа) = strftime('%Y-%m', 'now')
    GROUP BY к.id
    ORDER BY общая_сумма DESC
    LIMIT 1;
''')
result = cursor.fetchone()
print("\n2. Клиент с наибольшей суммой заказов в этом месяце:")
if result:
    print(f"   {result[0]} - {result[1]:.2f} руб.")
else:
    print("   Нет заказов в этом месяце")



cursor.execute('''
    SELECT 
        з.id as номер_заказа,
        кл.имя || ' ' || кл.фамилия as клиент,
        з.сумма,
        з.статус,
        з.способ_оплаты,
        кур.транспорт
    FROM заказы з
    LEFT JOIN клиенты кл ON з.клиент_id = кл.id
    LEFT JOIN курьеры кур ON з.курьер_id = кур.id
    WHERE date(з.дата_заказа) = date('now')
    ORDER BY з.дата_заказа;
''')
results = cursor.fetchall()
print("\n3. Заказы за сегодня:")
if results:
    for row in results:
        транспорт = f", {row[5]}" if row[5] else ""
        print(f"   Заказ №{row[0]}: {row[1]}, {row[2]:.2f} руб., {row[3]}, {row[4]}{транспорт}")


cursor.close()
conn.close()