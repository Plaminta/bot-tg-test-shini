import aiosqlite
from datetime import datetime, timedelta
from config import DB_NAME

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, username TEXT, age INTEGER, gender TEXT, looking_for TEXT,
                city TEXT, name TEXT, bio TEXT, photo_id TEXT, categories TEXT, is_active INTEGER DEFAULT 1,
                is_blocked INTEGER DEFAULT 0, has_seen_ad INTEGER DEFAULT 0, is_premium INTEGER DEFAULT 0,
                chat_gender_pref TEXT DEFAULT 'all', referrer_id INTEGER DEFAULT NULL, premium_until TEXT DEFAULT NULL,
                tag TEXT DEFAULT NULL, hide_prem INTEGER DEFAULT 0, coins INTEGER DEFAULT 100,
                farm_level INTEGER DEFAULT 1, last_farm_claim TEXT DEFAULT NULL, hide_age INTEGER DEFAULT 0,
                vip_badge INTEGER DEFAULT 0, ghost_mode INTEGER DEFAULT 0, prem_level INTEGER DEFAULT 0
            )
        """)
        
        try:
            await db.execute("ALTER TABLE users ADD COLUMN prem_type TEXT DEFAULT NULL")
        except:
            pass

        await db.execute("CREATE TABLE IF NOT EXISTS likes (from_id INTEGER, to_id INTEGER, PRIMARY KEY (from_id, to_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS skips (from_id INTEGER, to_id INTEGER, PRIMARY KEY (from_id, to_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS daily_likes (user_id INTEGER, date TEXT, count INTEGER DEFAULT 0, PRIMARY KEY (user_id, date))")
        await db.execute("CREATE TABLE IF NOT EXISTS achievements (user_id INTEGER, level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0, PRIMARY KEY (user_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS chat_queue (user_id INTEGER PRIMARY KEY, gender_pref TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS active_chats (user1_id INTEGER PRIMARY KEY, user2_id INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS promocodes (code TEXT PRIMARY KEY, days INTEGER, max_uses INTEGER, used_count INTEGER DEFAULT 0)")
        await db.execute("CREATE TABLE IF NOT EXISTS bonuses (user_id INTEGER PRIMARY KEY, last_claim TEXT, streak INTEGER DEFAULT 0)")
        await db.execute("CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item_id TEXT, purchase_date TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS stocks (user_id INTEGER, stock_id TEXT, amount INTEGER)")
        
        columns_to_add = [
            ("coins", "INTEGER DEFAULT 100"), ("farm_level", "INTEGER DEFAULT 1"),
            ("last_farm_claim", "TEXT DEFAULT NULL"), ("hide_age", "INTEGER DEFAULT 0"),
            ("vip_badge", "INTEGER DEFAULT 0"), ("ghost_mode", "INTEGER DEFAULT 0"),
            ("prem_level", "INTEGER DEFAULT 0")
        ]
        for col_name, col_type in columns_to_add:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            except:
                pass
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()

async def save_user(user_id, username, age, gender, looking_for, city, name, bio, photo_id, categories, referrer_id=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username, age, gender, looking_for, city, name, bio, photo_id, categories, is_active, is_blocked, has_seen_ad, is_premium, chat_gender_pref, referrer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 0, 'all', ?)
        """, (user_id, username, age, gender, looking_for, city, name, bio, photo_id, categories, referrer_id))
        await db.execute("INSERT OR IGNORE INTO achievements (user_id, level, exp) VALUES (?, 1, 0)", (user_id,))
        await db.commit()

async def block_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_active = 0, is_blocked = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def deactivate_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
        await db.commit()

async def mark_ad_seen(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET has_seen_ad = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def add_exp(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT level, exp FROM achievements WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                await db.execute("INSERT INTO achievements (user_id, level, exp) VALUES (?, 1, ?)", (user_id, amount))
            else:
                lvl, exp = row
                new_exp = exp + amount
                while new_exp >= (lvl * 100):
                    new_exp -= (lvl * 100)
                    lvl += 1
                await db.execute("UPDATE achievements SET level = ?, exp = ? WHERE user_id = ?", (lvl, new_exp, user_id))
        await db.commit()

async def get_level_info(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT level, exp FROM achievements WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row if row else (1, 0)

async def get_stats(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM likes WHERE from_id = ?", (user_id,)) as cur:
            likes_given = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM likes WHERE to_id = ?", (user_id,)) as cur:
            likes_received = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM skips WHERE to_id = ?", (user_id,)) as cur:
            skips_received = (await cur.fetchone())[0]
        views = likes_received + skips_received
        conversion = int((likes_received / views * 100)) if views > 0 else 0
        async with db.execute("SELECT COUNT(*) FROM users WHERE (SELECT COUNT(*) FROM likes WHERE to_id = users.user_id) > ?", (likes_received,)) as cur:
            better_users = (await cur.fetchone())[0]
            position = better_users + 1
    return {"likes_given": likes_given, "likes_received": likes_received, "skips_received": skips_received, "views": views, "conversion": conversion, "position": position}

async def get_next_profile(user_id, my_gender, my_pref, my_city, my_categories, my_prem_type=None):
    async with aiosqlite.connect(DB_NAME) as db:
        base_query = """
            SELECT * FROM users 
            WHERE user_id != ? AND is_active = 1 AND is_blocked = 0 
            AND user_id NOT IN (SELECT to_id FROM likes WHERE from_id = ?)
            AND user_id NOT IN (SELECT to_id FROM skips WHERE from_id = ?)
        """
        params = [user_id, user_id, user_id]
        
        if my_pref != 'all':
            base_query += " AND gender = ?"
            params.append(my_pref)
            
        if my_gender != 'all':
            base_query += " AND (looking_for = 'all' OR looking_for = ?)"
            params.append(my_gender)
        
        if my_prem_type == "standard":
            base_query += " AND (prem_type IS NULL OR prem_type = '')"
            
        query_prem_city = base_query + " AND city = ? AND is_premium = 1"
        async with db.execute(query_prem_city, params + [my_city]) as cur:
            prem = await cur.fetchone()
            if prem: return prem, True

        query_city = base_query + " AND city = ?"
        async with db.execute(query_city, params + [my_city]) as cur:
            profiles = await cur.fetchall()
            
        if not profiles:
            query_prem_all = base_query + " AND is_premium = 1"
            async with db.execute(query_prem_all, params) as cur:
                prem_all = await cur.fetchone()
                if prem_all: return prem_all, True

            query_all = base_query
            async with db.execute(query_all, params) as cur:
                profiles = await cur.fetchall()
                
        if not profiles: return None, False

        my_cats = set([c.strip() for c in my_categories.split(',')]) if my_categories else set()
        best_profile = None
        max_matches = -1
        
        for p in profiles:
            p_cats = set([c.strip() for c in p[9].split(',')]) if p[9] else set()
            matches = len(my_cats.intersection(p_cats))
            if matches > max_matches:
                max_matches = matches
                best_profile = p
                
        return best_profile, False

async def add_like(from_id, to_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO likes (from_id, to_id) VALUES (?, ?)", (from_id, to_id))
        await db.commit()
        await add_exp(from_id, 10)
        async with db.execute("SELECT 1 FROM likes WHERE from_id = ? AND to_id = ?", (to_id, from_id)) as cur:
            return await cur.fetchone() is not None

async def add_skip(from_id, to_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO skips (from_id, to_id) VALUES (?, ?)", (from_id, to_id))
        await db.commit()

async def count_likers(target_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM likes WHERE to_id = ?", (target_id,)) as cur:
            res = await cur.fetchone()
            return res[0] if res else 0

async def get_unread_like(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT from_id FROM likes WHERE to_id = ? AND from_id NOT IN (SELECT to_id FROM likes WHERE from_id = ?) LIMIT 1", (user_id, user_id)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def get_all_likers(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT u.* FROM users u 
            JOIN likes l ON u.user_id = l.from_id 
            WHERE l.to_id = ? AND u.user_id NOT IN (SELECT to_id FROM likes WHERE from_id = ?)
        """, (user_id, user_id)) as cur:
            return await cur.fetchall()

async def check_premium_status(user_id):
    user = await get_user(user_id)
    if not user: return None
    
    is_active_date = False
    if user[14]:
        try:
            prem_date = datetime.strptime(user[14], "%Y-%m-%d %H:%M:%S")
            if prem_date > datetime.now(): 
                is_active_date = True
        except: pass
        
    if is_active_date or user[13] == 1:
        p_type = user[19] 
        if isinstance(p_type, str) and p_type in ["standard", "deluxe"]:
            return p_type
        return "standard" 
        
    return None

async def set_premium(user_id, days, prem_type="standard"):
    prem_until = datetime.now() + timedelta(days=days)
    prem_str = prem_until.strftime("%Y-%m-%d %H:%M:%S")
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE users 
            SET is_premium = 1, premium_until = ?, prem_type = ? 
            WHERE user_id = ?
        """, (prem_str, prem_type, user_id))
        await db.commit()

def get_declension(count, gender):
    if gender == "girl":
        if count % 10 == 1 and count % 100 != 11: 
            return "девушке"
        elif 2 <= count % 10 <= 4 and not (12 <= count % 100 <= 14): 
            return "девушкам"
        else: 
            return "девушкам"
    else:
        if count % 10 == 1 and count % 100 != 11: 
            return "парню"
        elif 2 <= count % 10 <= 4 and not (12 <= count % 100 <= 14): 
            return "парням"
        else: 
            return "парням"

def get_pronoun(gender): 
    return "её" if gender == "girl" else "его"