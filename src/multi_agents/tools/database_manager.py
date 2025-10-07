# database_manager.py
import duckdb
from pathlib import Path

def _safe_exec(con: duckdb.DuckDBPyConnection, sql: str) -> None:
    try:
        con.execute(sql)
    except Exception:
        # ignore if constraint/index already exists or if an optional FK fails
        pass

def load_data_into_duckdb(json_path: Path, db_path: Path, mode: str = "posts") -> None:
    """
    Loads Apify instagram-scraper JSON into DuckDB with sane schemas.

    mode = "posts"   -> create posts / comments / images (and link comments/images -> posts)
    mode = "details" -> create instagram_profiles (profile metadata)
    """
    print("\n>>> Connecting to DuckDB and creating final tables directly...")
    print(f"    Database file will be at: {db_path}")

    con = None
    try:
        con = duckdb.connect(database=str(db_path), read_only=False)

        if mode == "posts":
            # 1) POSTS
            print("    - Creating 'posts' table with Primary Key...")
            con.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id              VARCHAR PRIMARY KEY,
                    type            VARCHAR,
                    shortCode       VARCHAR,
                    caption         VARCHAR,
                    url             VARCHAR,
                    commentsCount   INTEGER,
                    likesCount      INTEGER,
                    -- Apify usually returns UNIX seconds; adjust if ms
                    timestamp       TIMESTAMP,
                    displayUrl      VARCHAR,
                    alt             VARCHAR,
                    ownerFullName   VARCHAR,
                    ownerUsername   VARCHAR,
                    ownerId         VARCHAR,
                    isSponsored     BOOLEAN,
                    isPinned        BOOLEAN
                );
            """)

            # Upsert (dedupe by id). DuckDB has MERGE; keep it simple with anti-join
            con.execute(f"""
                INSERT INTO posts
                SELECT
                    id,
                    type,
                    shortCode,
                    caption,
                    url,
                    commentsCount,
                    likesCount,
                    CASE
                        WHEN typeof(timestamp) IN ('INTEGER','BIGINT','HUGEINT','UTINYINT','TINYINT','SMALLINT','UBIGINT','UINTEGER')
                            THEN to_timestamp(CAST(timestamp AS BIGINT))         -- seconds
                        WHEN typeof(timestamp) = 'VARCHAR'
                            THEN try_strptime(timestamp, '%Y-%m-%d %H:%M:%S')     -- fallback if already a string
                        ELSE NULL
                    END AS timestamp,
                    displayUrl,
                    alt,
                    ownerFullName,
                    ownerUsername,
                    ownerId,
                    COALESCE(isSponsored, FALSE) AS isSponsored,
                    COALESCE(isPinned, FALSE)     AS isPinned
                FROM (
                    SELECT
                        id, type, shortCode, caption, url, commentsCount, likesCount,
                        timestamp, displayUrl, alt, ownerFullName, ownerUsername,
                        ownerId, isSponsored, isPinned
                    FROM read_json_auto('{json_path.as_posix()}')
                ) src
                WHERE NOT EXISTS (SELECT 1 FROM posts p WHERE p.id = src.id);
            """)

            # 2) COMMENTS
            print("    - Creating 'comments' table...")
            con.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    comment_id              VARCHAR PRIMARY KEY,
                    post_id                 VARCHAR,
                    comment_text            VARCHAR,
                    comment_timestamp       TIMESTAMP,
                    comment_likes_count     INTEGER,
                    owner_username          VARCHAR,
                    owner_id                VARCHAR,
                    owner_profile_pic_url   VARCHAR
                );
            """)
            # Insert comments (skip if none)
            _safe_exec(con, f"""
                INSERT INTO comments
                SELECT
                    c.id                                           AS comment_id,
                    p.id                                           AS post_id,
                    c.text                                         AS comment_text,
                    CASE
                        WHEN typeof(c.timestamp) IN ('INTEGER','BIGINT','HUGEINT') THEN to_timestamp(CAST(c.timestamp AS BIGINT))
                        WHEN typeof(c.timestamp) = 'VARCHAR' THEN try_strptime(c.timestamp, '%Y-%m-%d %H:%M:%S')
                        ELSE NULL
                    END                                             AS comment_timestamp,
                    c.likesCount                                    AS comment_likes_count,
                    c.owner.username                                AS owner_username,
                    c.owner.id                                      AS owner_id,
                    c.owner.profile_pic_url                         AS owner_profile_pic_url
                FROM read_json_auto('{json_path.as_posix()}') AS p,
                     UNNEST(p.latestComments) AS t(c)
                WHERE c.id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM comments cc WHERE cc.comment_id = c.id);
            """)

            # 3) IMAGES
            print("    - Creating 'images' table...")
            con.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    post_id        VARCHAR,
                    ownerId        VARCHAR,
                    ownerUsername  VARCHAR,
                    image_url      VARCHAR,
                    -- Composite PK: one row per (post_id, image_url)
                    PRIMARY KEY (post_id, image_url)
                );
            """)
            _safe_exec(con, f"""
                INSERT INTO images
                SELECT
                    p.id                AS post_id,
                    p.ownerId           AS ownerId,
                    p.ownerUsername     AS ownerUsername,
                    image_url
                FROM read_json_auto('{json_path.as_posix()}') AS p,
                     UNNEST(p.images) AS t(image_url)
                WHERE image_url IS NOT NULL
                  AND NOT EXISTS (
                        SELECT 1 FROM images i
                        WHERE i.post_id = p.id AND i.image_url = image_url
                  );
            """)

            # Foreign keys AFTER tables exist (optional; DuckDB supports FKs, but keep tolerant)
            _safe_exec(con, """
                ALTER TABLE comments
                ADD CONSTRAINT fk_comments_post
                FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE;
            """)
            _safe_exec(con, """
                ALTER TABLE images
                ADD CONSTRAINT fk_images_post
                FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE;
            """)

            # Indexes to speed joins/filters
            _safe_exec(con, "CREATE INDEX idx_posts_owner ON posts(ownerUsername);")
            _safe_exec(con, "CREATE INDEX idx_comments_post ON comments(post_id);")
            _safe_exec(con, "CREATE INDEX idx_images_post ON images(post_id);")

            # Verification
            post_count    = con.execute("SELECT COUNT(*) FROM posts;").fetchone()[0]
            comment_count = con.execute("SELECT COUNT(*) FROM comments;").fetchone()[0]
            image_count   = con.execute("SELECT COUNT(*) FROM images;").fetchone()[0]
            print("\n    Verification successful:")
            print(f"    - Loaded {post_count} posts.")
            print(f"    - Loaded {comment_count} comments.")
            print(f"    - Loaded {image_count} images.")

        elif mode == "details":
            # 4) INSTAGRAM PROFILES
            print("    - Creating 'instagram_profiles' table...")
            con.execute("""
                CREATE TABLE IF NOT EXISTS instagram_profiles (
                    owner_id                VARCHAR PRIMARY KEY,
                    username                VARCHAR,
                    full_name               VARCHAR,
                    biography               VARCHAR,
                    external_url            VARCHAR,
                    followers_count         BIGINT,
                    follows_count           BIGINT,
                    has_channel             BOOLEAN,
                    highlight_reel_count    BIGINT,
                    is_business_account     BOOLEAN,
                    joined_recently         BOOLEAN,
                    business_category_name  VARCHAR,
                    is_private              BOOLEAN,
                    is_verified             BOOLEAN,
                    profile_pic_url         VARCHAR,
                    profile_pic_url_hd      VARCHAR,
                    igtv_video_count        BIGINT,
                    posts_count             BIGINT,
                    scraped_at              TIMESTAMP DEFAULT now(),
                    input_url               VARCHAR
                );
            """)

            # Insert (dedupe by owner_id)
            con.execute(f"""
                INSERT INTO instagram_profiles
                SELECT
                    id                                           AS owner_id,
                    username                                     AS username,
                    fullName                                     AS full_name,
                    biography                                    AS biography,
                    externalUrl                                  AS external_url,
                    followersCount                               AS followers_count,
                    followsCount                                 AS follows_count,
                    hasChannel                                   AS has_channel,
                    highlightReelCount                           AS highlight_reel_count,
                    isBusinessAccount                            AS is_business_account,
                    joinedRecently                               AS joined_recently,
                    businessCategoryName                         AS business_category_name,
                    private                                      AS is_private,
                    verified                                     AS is_verified,
                    profilePicUrl                                AS profile_pic_url,
                    COALESCE(profilePicUrlHD, profilePicUrl)     AS profile_pic_url_hd,
                    igtvVideoCount                               AS igtv_video_count,
                    postsCount                                   AS posts_count,
                    now()                                        AS scraped_at,
                    inputUrl                                     AS input_url
                FROM read_json_auto('{json_path.as_posix()}') src
                WHERE id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM instagram_profiles p WHERE p.owner_id = src.id);
            """)

            # Helpful index
            _safe_exec(con, "CREATE INDEX idx_profiles_username ON instagram_profiles(username);")

            profile_count = con.execute("SELECT COUNT(*) FROM instagram_profiles;").fetchone()[0]
            print("\n    Verification successful:")
            print(f"    - Loaded {profile_count} profile(s).")

        else:
            print(f"Unknown mode: {mode}")

    except Exception as e:
        print(f"An error occurred with DuckDB: {e}")
    finally:
        if con:
            con.close()
            print("    Database connection closed.")
