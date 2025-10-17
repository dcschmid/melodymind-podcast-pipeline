# Mehrsprachige Nutzung der MelodyMind Pipeline

## Verzeichnisstruktur

Das System unterstützt jetzt mehrere Sprachen mit folgender Struktur:

```
inputs/
  [decade]/
    de/           # Deutsch
      audio/wav/
      images/
    en/           # Englisch
      audio/wav/
      images/
    es/           # Spanisch
      audio/wav/
      images/
    fr/           # Französisch
      audio/wav/
      images/
    it/           # Italienisch
      audio/wav/
      images/
    pt/           # Portugiesisch
      audio/wav/
      images/

outputs/
  [decade]/
    de/           # Deutsche Ausgabe
    en/           # Englische Ausgabe
    es/           # Spanische Ausgabe
    fr/           # Französische Ausgabe
    it/           # Italienische Ausgabe
    pt/           # Portugiesische Ausgabe
```

## Unterstützte Sprachen

- `de`: Deutsch (Standard)
- `en`: Englisch
- `es`: Spanisch
- `fr`: Französisch
- `it`: Italienisch
- `pt`: Portugiesisch

## Verwendung

### Grundlegende Verwendung

```bash
# Deutsche Version (Standard)
python melody_mind_split.py --decade 1960s --language de

# Englische Version
python melody_mind_split.py --decade 1960s --language en

# Spanische Version
python melody_mind_split.py --decade 1960s --language es

# Weitere Sprachen analog...
```

### Beispiel mit weiteren Parametern

```bash
# Englische Version mit spezifischen Einstellungen
python melody_mind_split.py \
  --decade 1960s \
  --language en \
  --fps 30 \
  --enhancer gfpgan \
  --ducking \
  --verbose
```

## Audio-Dateien

Lege deine Audio-Dateien in das entsprechende Sprachverzeichnis:

- Deutsche Audio-Dateien: `inputs/1960s/de/audio/`
- Englische Audio-Dateien: `inputs/1960s/en/audio/`
- Etc.

Die Dateien müssen wie gewohnt benannt werden:
- `segment01_daniel.mp3`
- `segment01_annabelle.mp3`
- `segment02_daniel.mp3`
- `segment02_annabelle.mp3`

## Bilder

Die Charakterbilder (`daniel.png`, `annabelle.png`) wurden automatisch in alle Sprachverzeichnisse kopiert.

Falls du sprachspezifische Bilder verwenden möchtest, ersetze sie einfach in den jeweiligen `images/` Verzeichnissen.

## Ausgabe

Die finalen Videos werden sprachspezifisch benannt:
- `outputs/1960s/de/finished/1960s_de.mp4`
- `outputs/1960s/en/finished/1960s_en.mp4`
- `outputs/1960s/es/finished/1960s_es.mp4`
- Etc.

## Tipps

1. Du kannst die gleichen Audio-Segmente in verschiedenen Sprachen verarbeiten
2. Jede Sprache hat ihre eigenen Cache-Verzeichnisse (SadTalker-Ausgaben)
3. Das System erstellt automatisch alle notwendigen Verzeichnisse
4. Die Standard-Sprache ist Deutsch (`de`)