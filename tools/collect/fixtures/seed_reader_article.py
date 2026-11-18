#!/usr/bin/env python3
"""Add one feed and its articles to an initialized Sheaf-Reader database.

The input is the app's own empty `sheaf_reader.db` (launch the app once, stop it,
then copy the database out). The output is an ordinary database: one subscription
and either one long article (reader case) or many ordinary articles (search case),
with HTML text bodies and no images or links to fetch.

  sheafreader_reader_body_reparse:  seed_reader_article.py empty.db long.db
  sheafreader_search_no_debounce:   seed_reader_article.py empty.db many.db --articles 1000 --paragraphs 6
The feed was "just fetched" and refreshes hourly, so opening the app does not
start a network refresh.
"""
import argparse
import hashlib
import shutil
import sqlite3
import time
from pathlib import Path

WORDS = ('river light archive measure harbor signal winter garden quiet engine '
         'letter morning paper bridge summer market island thread window record').split()


def body(paragraphs):
    parts = []
    for p in range(paragraphs):
        words = [WORDS[(p * 7 + i * 3) % len(WORDS)] for i in range(90)]
        text = ' '.join(words).capitalize()
        # Ordinary inline markup and entities that the reader has to decode.
        parts.append(f'<p>{text} &amp; <b>note {p}</b> &mdash; <i>part {p % 12}</i>.</p>')
        if p % 25 == 0:
            parts.append(f'<h2>Section {p // 25 + 1}</h2>')
    return '\n'.join(parts)


def seed(empty, out, paragraphs, articles=1):
    """One long article (default), or `articles` ordinary articles of `paragraphs` each."""
    shutil.copyfile(empty, out)
    now = int(time.time() * 1000)
    html = body(paragraphs)
    with sqlite3.connect(out) as db:
        if db.execute('SELECT COUNT(*) FROM feeds').fetchone()[0]:
            raise SystemExit('input database is not empty')
        db.execute("INSERT INTO feeds (url, title, link, last_fetched, fetch_frequency) VALUES (?,?,?,?,?)",
                   ('http://127.0.0.1:9/longform.xml', 'Longform Journal', 'http://127.0.0.1:9/', now, 60))
        if articles == 1:
            rows = [('Long Article', 'http://127.0.0.1:9/long-article', 'Editor', html,
                     'A long article', now - 3600_000, now, 'long-article-1')]
        else:
            rows = []
            for i in range(articles):
                title = f'{WORDS[i % len(WORDS)].capitalize()} {WORDS[(i * 7) % len(WORDS)]} report {i + 1}'
                rows.append((title, f'http://127.0.0.1:9/article-{i + 1}', 'Editor', html,
                             f'Notes about {WORDS[(i * 3) % len(WORDS)]} and {WORDS[(i * 11) % len(WORDS)]}',
                             now - (i + 1) * 60_000, now, f'article-{i + 1}'))
        db.executemany("INSERT INTO articles (feed_id, title, link, author, content, snippet, published, fetched, read, guid) "
                       "VALUES (1,?,?,?,?,?,?,?,1,?)", rows)
    return len(html) * articles, hashlib.sha256(Path(out).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('empty_db', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--paragraphs', type=int, default=400, help='paragraphs per article body')
    ap.add_argument('--articles', type=int, default=1,
                    help='1: one long article "Long Article"; N>1: N ordinary articles')
    a = ap.parse_args()
    size, sha = seed(a.empty_db, a.out, a.paragraphs, a.articles)
    print(f'{a.out}: {a.articles} article(s), {size} body bytes, sha256 {sha}')


if __name__ == '__main__':
    main()
