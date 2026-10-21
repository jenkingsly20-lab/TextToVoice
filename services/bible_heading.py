"""Recognize only a complete Bible reference on the first nonempty line."""
import re
from indic_numtowords import num2words

BOOKS = set('ஆதியாகமம்|யாத்திராகமம்|லேவியராகமம்|எண்ணாகமம்|உபாகமம்|யோசுவா|நியாயாதிபதிகள்|ரூத்|சாமுவேல்|இராஜாக்கள்|ராஜாக்கள்|நாளாகமம்|எஸ்றா|நெகேமியா|எஸ்தர்|யோபு|சங்கீதம்|சங்கீதங்கள்|நீதிமொழிகள்|பிரசங்கி|உன்னதப்பாட்டு|ஏசாயா|எரேமியா|புலம்பல்|புலம்பல்கள்|எசேக்கியேல்|தானியேல்|ஓசியா|யோவேல்|ஆமோஸ்|ஒபதியா|யோனா|மீகா|நாகூம்|ஆபகூக்|செப்பனியா|ஆகாய்|சகரியா|மல்கியா|மத்தேயு|மாற்கு|லூக்கா|யோவான்|அப்போஸ்தலர்|அப்போஸ்தலருடைய நடபடிகள்|ரோமர்|கொரிந்தியர்|கலாத்தியர்|எபேசியர்|பிலிப்பியர்|கொலோசெயர்|தெசலோனிக்கேயர்|தீமோத்தேயு|தீத்து|பிலேமோன்|எபிரெயர்|யாக்கோபு|பேதுரு|யூதா|வெளிப்படுத்தல்|வெளிப்படுத்தின விசேஷம்'.split('|'))
PREFIXED = {'சாமுவேல்':2,'இராஜாக்கள்':2,'ராஜாக்கள்':2,'நாளாகமம்':2,
            'கொரிந்தியர்':2,'தெசலோனிக்கேயர்':2,'தீமோத்தேயு':2,'பேதுரு':2,'யோவான்':3}
D = r'[0-9௦-௯]+'
REFERENCE = re.compile(r'(?:(?P<prefix>[1-3௧-௩])\s+)?(?P<book>[^0-9௦-௯:]+?)\s+(?P<chapter>'+D+r')(?:\s*:\s*(?P<verse>'+D+r')(?:\s*[-–—]\s*(?P<end>'+D+r'))?)?\.?')
ORDINAL = {1:'முதலாம்',2:'இரண்டாம்',3:'மூன்றாம்',4:'நான்காம்',5:'ஐந்தாம்',6:'ஆறாம்',7:'ஏழாம்',8:'எட்டாம்',9:'ஒன்பதாம்',10:'பத்தாம்',11:'பதினொன்றாம்',12:'பன்னிரண்டாம்',13:'பதின்மூன்றாம்',14:'பதினான்காம்',15:'பதினைந்தாம்',16:'பதினாறாம்',17:'பதினேழாம்',18:'பதினெட்டாம்',19:'பத்தொன்பதாம்',20:'இருபதாம்',30:'முப்பதாம்',40:'நாற்பதாம்',50:'ஐம்பதாம்',60:'அறுபதாம்',70:'எழுபதாம்',80:'எண்பதாம்',90:'தொண்ணூறாம்',100:'நூறாம்'}

def cardinal(number):
    return num2words(number,lang='ta').replace('\u200c','').strip()

# num2words returns joined, partly colloquial/misspelled single words for 91–99
# (e.g. 98 -> தொண்ணூரெட்டு), so these ordinals are spelled out explicitly.
ORDINAL.update({91:'தொண்ணூற்றொன்றாம்',92:'தொண்ணூற்றிரண்டாம்',95:'தொண்ணூற்றைந்தாம்',
    96:'தொண்ணூற்றாறாம்',97:'தொண்ணூற்றேழாம்',98:'தொண்ணூற்றெட்டாம்',99:'தொண்ணூற்றொன்பதாம்'})

def ordinal(number):
    if number in ORDINAL:
        return ORDINAL[number]
    words = cardinal(number).split()
    if len(words) == 1:
        word = words[0]
        return (word[:-1] + 'ாம்') if word.endswith('ு') else word + 'ஆம்'
    # Join the final component into its ordinal without applying number rules
    # to any scripture words (e.g. இருபத்து மூன்று -> இருபத்துமூன்றாம்).
    tail = number % 100
    if tail in ORDINAL and tail >= 10:
        words[-1] = ORDINAL[tail]
        return ' '.join(words)
    unit = number % 10
    prefix = words[-2]
    joined_vowels = {1:'ொன்றாம்',2:'ிரண்டாம்',5:'ைந்தாம்',6:'ாறாம்',7:'ேழாம்',8:'ெட்டாம்',9:'ொன்பதாம்'}
    if unit in joined_vowels and prefix.endswith('ு'):
        last = prefix[:-1]+joined_vowels[unit]
    else:
        last = prefix+ORDINAL[unit]
    return ' '.join(words[:-2]+[last])

# English (WEB) book names in canonical order: (written name, spoken name, book id).
# Ids match the Tamil BOOK_IDS so both languages share file names (john_03.mp3).
ENGLISH_BOOKS = [(name, spoken or name, book_id) for name, spoken, book_id in [
    ('Genesis','','genesis'),('Exodus','','exodus'),('Leviticus','','leviticus'),('Numbers','','numbers'),
    ('Deuteronomy','','deuteronomy'),('Joshua','','joshua'),('Judges','','judges'),('Ruth','','ruth'),
    ('1 Samuel','First Samuel','1samuel'),('2 Samuel','Second Samuel','2samuel'),('1 Kings','First Kings','1kings'),
    ('2 Kings','Second Kings','2kings'),('1 Chronicles','First Chronicles','1chronicles'),
    ('2 Chronicles','Second Chronicles','2chronicles'),('Ezra','','ezra'),('Nehemiah','','nehemiah'),
    ('Esther','','esther'),('Job','','job'),('Psalms','','psalms'),('Proverbs','','proverbs'),
    ('Ecclesiastes','','ecclesiastes'),('Song of Solomon','','songofsolomon'),('Isaiah','','isaiah'),
    ('Jeremiah','','jeremiah'),('Lamentations','','lamentations'),('Ezekiel','','ezekiel'),('Daniel','','daniel'),
    ('Hosea','','hosea'),('Joel','','joel'),('Amos','','amos'),('Obadiah','','obadiah'),('Jonah','','jonah'),
    ('Micah','','micah'),('Nahum','','nahum'),('Habakkuk','','habakkuk'),('Zephaniah','','zephaniah'),
    ('Haggai','','haggai'),('Zechariah','','zechariah'),('Malachi','','malachi'),('Matthew','','matthew'),
    ('Mark','','mark'),('Luke','','luke'),('John','','john'),('Acts','','acts'),('Romans','','romans'),
    ('1 Corinthians','First Corinthians','1corinthians'),('2 Corinthians','Second Corinthians','2corinthians'),
    ('Galatians','','galatians'),('Ephesians','','ephesians'),('Philippians','','philippians'),
    ('Colossians','','colossians'),('1 Thessalonians','First Thessalonians','1thessalonians'),
    ('2 Thessalonians','Second Thessalonians','2thessalonians'),('1 Timothy','First Timothy','1timothy'),
    ('2 Timothy','Second Timothy','2timothy'),('Titus','','titus'),('Philemon','','philemon'),
    ('Hebrews','','hebrews'),('James','','james'),('1 Peter','First Peter','1peter'),('2 Peter','Second Peter','2peter'),
    ('1 John','First John','1john'),('2 John','Second John','2john'),('3 John','Third John','3john'),
    ('Jude','','jude'),('Revelation','','revelation')]]
ENGLISH_REFERENCE = re.compile(r'(?P<book>(?:[1-3] )?[A-Za-z][A-Za-z ]*?)\s+(?P<chapter>\d+)\.?')

def extract_english_heading(text):
    """'John 3' on the first nonempty line -> spoken 'John, chapter 3.' ('Psalm 23.')."""
    offset = 0
    names = {name: (spoken, book_id) for name, spoken, book_id in ENGLISH_BOOKS}
    for line in text.splitlines(keepends=True):
        candidate = line.rstrip('\r\n')
        if not candidate.strip('﻿ \t'):
            offset += len(line)
            continue
        match = ENGLISH_REFERENCE.fullmatch(candidate.strip('﻿ \t'))
        if not match or ' '.join(match['book'].split()) not in names or not 1 <= int(match['chapter']) <= 150:
            return None
        spoken_book, book_id = names[' '.join(match['book'].split())]
        chapter = int(match['chapter'])
        spoken = f'Psalm {chapter}.' if book_id == 'psalms' else f'{spoken_book}, chapter {chapter}.'
        return dict(book=spoken_book, book_id=book_id, book_prefix=None, chapter=chapter, verse=None, verse_end=None,
                    start=offset, end=offset+len(candidate), body_start=offset+len(line),
                    original=candidate, spoken=spoken)
    return None

def extract_heading(text, language='ta'):
    if language == 'en':
        return extract_english_heading(text)
    offset = 0
    for line in text.splitlines(keepends=True):
        candidate = line.rstrip('\r\n')
        if not candidate.strip('\ufeff \t'):
            offset += len(line)
            continue
        match = REFERENCE.fullmatch(candidate.strip('\ufeff \t'))
        if not match:
            return None
        book = ' '.join(match['book'].split())
        if book not in BOOKS:
            return None
        prefix = int(match['prefix']) if match['prefix'] else None
        if prefix and prefix > PREFIXED.get(book,0):
            return None
        chapter = int(match['chapter'])
        verse = int(match['verse']) if match['verse'] else None
        end = int(match['end']) if match['end'] else None
        if not 1 <= chapter <= 150 or (verse is not None and not 1 <= verse <= 176) or (end is not None and not verse <= end <= 176):
            return None
        spoken_book = (ordinal(prefix)+' ' if prefix else '')+book
        if book in ('சங்கீதம்','சங்கீதங்கள்'):
            spoken = ordinal(chapter)+' சங்கீதம்'
        else:
            spoken = spoken_book+', '+ordinal(chapter)+' அதிகாரம்'
        if end is not None and end != verse:
            spoken += ', '+cardinal(verse)+' முதல் '+cardinal(end)+' வரையிலான வசனங்கள்'
        elif verse is not None:
            spoken += ', '+ordinal(verse)+' வசனம்'
        return dict(book=book,book_prefix=prefix,chapter=chapter,verse=verse,verse_end=end,
                    start=offset,end=offset+len(candidate),body_start=offset+len(line),
                    original=candidate,spoken=spoken+'.')
    return None
