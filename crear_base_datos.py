import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect('gastos.db')
c = conn.cursor()

# Crear tablas si no existen
c.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    email TEXT NOT NULL,
    password TEXT NOT NULL
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS categorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS gastos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL,
    monto REAL NOT NULL,
    descripcion TEXT,
    fecha TEXT NOT NULL,
    usuario_id INTEGER,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
)
''')

# Añadir categorías predeterminadas si no existen
categorias_predeterminadas = ['Alimentos', 'Transporte', 'Entretenimiento', 'Salud', 'Vivienda']
for categoria in categorias_predeterminadas:
    c.execute('INSERT OR IGNORE INTO categorias (nombre) VALUES (?)', (categoria,))

conn.commit()
conn.close()
