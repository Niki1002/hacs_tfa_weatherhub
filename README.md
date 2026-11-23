# TFA weatherhub für Home Assistant

Custom Integration für das **TFA Dostmann weatherhub** System, z. B. das
Wetterstation-Set mit Klima-, Regen- und Windsender **31.4005.02**
(Gateway + Thermo-Hygro-Sender + Regensender 30.3306.02 + Windsender 30.3307.02).

Das weatherhub-Gateway überträgt die Messwerte an die Mobile-Alerts-Cloud
(`data199.com`). Diese Integration ruft die Werte dort über die öffentliche
REST-API ab. **Kein Account und kein API-Key nötig** – es reichen die Geräte-IDs.

## Entitäten

| Sender | Entitäten |
|---|---|
| Thermo-Hygro-Sender | Temperatur, Luftfeuchtigkeit |
| Regensender | Niederschlag gesamt (mm, `total_increasing`), ggf. Temperatur |
| Windsender | Windgeschwindigkeit, Windböen, Windrichtung (Grad + Himmelsrichtung) |
| alle | Batterie schwach (Binärsensor), Letzte Messung, Zuletzt gesehen (deaktiviert) |

Es werden nur Entitäten angelegt, für die der Sender auch Werte liefert.
Alle Sender werden mit **einer** API-Abfrage pro Intervall abgerufen.

## Installation

### HACS (empfohlen)
1. Dieses Repository auf GitHub hochladen.
2. HACS → ⋮ → *Benutzerdefinierte Repositories* → URL eintragen, Typ *Integration*.
3. „TFA weatherhub“ installieren und Home Assistant neu starten.

### Manuell
Den Ordner `custom_components/tfa_weatherhub` nach
`<config>/custom_components/tfa_weatherhub` kopieren und Home Assistant neu starten.

## Einrichtung

1. **Geräte-IDs heraussuchen:** Die 12-stellige ID (z. B. `0B12A3B4C5D6`) steht
   auf dem Aufkleber am Sender bzw. auf dem QR-Code und in der weatherhub-App
   unter dem jeweiligen Sensor → Einstellungen.
2. *Einstellungen → Geräte & Dienste → Integration hinzufügen → TFA weatherhub*.
3. Alle IDs eintragen (Komma oder Zeilenumbruch als Trenner).
4. Abfrageintervall wählen (Standard 5 min). Die Sender funken ohnehin nur etwa
   alle 7 Minuten; die API erlaubt maximal 3 Abfragen pro Minute.

IDs und Intervall lassen sich später über *Konfigurieren* ändern.

> Voraussetzung: Das Gateway ist mit dem Internet verbunden und die Sender
> erscheinen in der weatherhub-App.

## Tipps

**Regen pro Tag / Stunde** – der Regensender liefert eine Gesamtsumme.
Mit dem *Verbrauchszähler* (`utility_meter`) bekommst du Tageswerte:

```yaml
utility_meter:
  regen_heute:
    source: sensor.weatherhub_regensender_080000000000_niederschlag_gesamt
    cycle: daily
```

(Entity-ID an deine anpassen.)

## Entwicklung / Tests

```bash
pip install -r requirements_test.txt
pytest
```

## Hinweise

- Inoffizielles Projekt, nicht von TFA Dostmann oder Mobile Alerts.
- Abhängig von der Cloud-API; fällt diese aus, sind die Sensoren nicht verfügbar.
