# Welche Redmine-Daten der MCP-Server nutzt

Diese Seite beschreibt, welche Informationen aus Redmine und den Plugins `redmine_expert_helpdesk` (0.23) und
`redmine_expert_agile` (0.9) über den MCP-Server erreichbar sind, über welche REST-Endpunkte das passiert und
welche Rechte der Bot-User dafür braucht. Grundlage ist der Quellcode der Plugins; Endpunkte, die keine
API-Key-Anmeldung erlauben, sind für den Server nicht erreichbar.

Alles ist auf das beschränkt, was der Bot-User sehen darf: Projekte, in denen er Mitglied ist, und die Rechte
seiner Rolle. Antworten von Claude decken also nur diese Projekte ab.

## Grundsätzliches Verhalten

- **Listen sind gepaged:** Standard 25, maximal 100 Einträge pro Abfrage, mit `total_count` und `next_offset`.
  Lange Texte (Beschreibung, Kommentare) werden in Listen auf 300 Zeichen gekürzt, die Einzelabfrage liefert
  den vollen Text.
- **Unbekannte Filter ignoriert Redmine stillschweigend** und liefert dann ungefilterte Ergebnisse. Die Tools
  verwenden deshalb nur Filter, die es nachweislich gibt.
- **Nie zurückgegeben:** `api_key` und `password`, auch nicht in verschachtelten Daten.
- **Nie ausgelöst:** Mails an Kunden. Das Feld `helpdesk_init` wird abgelehnt, ebenso `uploads` (würde lokale
  Dateien lesen und hochladen).
- **Read-only-Modus (Standard):** keine Schreib-Tools, jeder Nicht-GET-Request wird vor dem Senden blockiert.

## Standard-Redmine (Toolset `standard`)

| Information | Tool | Endpunkt | Rechte (Rolle) |
|---|---|---|---|
| Eigener Bot-User, Mitgliedschaften | `get_current_user` | `GET /users/current.json` | – |
| Projekte, Projektdetails | `list_projects`, `get_project` | `/projects.json` | Projekt sichtbar |
| Issues filtern | `search_issues` | `GET /issues.json` | Tickets anzeigen |
| Issue mit Kommentaren, Anhängen, Beziehungen, Unteraufgaben, erlaubten Status | `get_issue` | `GET /issues/:id.json?include=…` | Tickets anzeigen |
| Zeiterfassung | `list_time_entries` | `GET /time_entries.json` | Aufwände anzeigen |
| Versionen, Mitglieder | `list_versions`, `list_project_members` | `/projects/:id/versions`, `/memberships` | Projekt sichtbar |
| Wiki | `list_wiki_pages`, `get_wiki_page` | `/projects/:id/wiki/…` | Wiki anzeigen |
| Volltextsuche | `search` | `GET /search.json` | je nach Objekt |
| Stammdaten (Status, Tracker, Prioritäten, Aktivitäten, gespeicherte Abfragen, Rollen) | `list_reference_data` | diverse | Custom Fields und Gruppen nur Admin |
| Anhang (Metadaten, Textinhalt bis 5 MB) | `get_attachment` | `/attachments/:id` | wie das Objekt |
| **Schreiben:** Issue anlegen/ändern/kommentieren, Zeit buchen, Beziehung, Wiki-Seite | `create_issue`, `update_issue`, `log_time`, `create_issue_relation`, `save_wiki_page` | `POST`/`PUT` | Tickets hinzufügen/bearbeiten, Notizen hinzufügen, Aufwände buchen, Wiki bearbeiten |

Filter für `search_issues` folgen der Redmine-Syntax mit Operator-Präfix: `~text` (enthält), `>=2026-01-01`,
`><von|bis`, `!5` (nicht), `*` (gesetzt), `!*` (leer), Custom Fields als `cf_<id>`.

## redmine_expert_helpdesk (Toolset `expert_helpdesk`)

Ein Helpdesk-Ticket ist ein normales Issue plus Kunde (Kontakt), Postfach, Mail-Protokoll und SLA-Zeiten.
Dazu kommt die Wissensbasis mit Problem/Lösung-Paaren aus geschlossenen Tickets.

### Was die Helpdesk-API liefert

| Information | Tool | Endpunkt | Rechte |
|---|---|---|---|
| Tickets eines Projekts (nur blättern, keine Filter) | `list_helpdesk_tickets` | `GET /projects/:id/helpdesk/tickets.json` | Tickets anzeigen, Modul Helpdesk aktiv |
| Ticket mit Kontakt, Postfach, SLA, Mail-Protokoll | `get_helpdesk_ticket` | `GET /helpdesk/tickets/:id.json?include=messages` | Tickets anzeigen |
| Kontakte suchen (Name, Mail, Firma) oder exakt per Mail | `list_helpdesk_contacts` | `GET /projects/:id/helpdesk/contacts.json?search=…\|email=…` | `view_helpdesk_info` oder `manage_helpdesk_contacts` |
| Kontakt | `get_helpdesk_contact` | `GET /helpdesk/contacts/:id.json` | wie oben |
| SLA-Zeiten pro Priorität, Autoresponder, Info-Anfragen, KI-Optionen | `get_helpdesk_project_settings` | `GET /projects/:id/helpdesk/settings.json` | `view_helpdesk_info` oder `manage_helpdesk` |
| Postfächer (ohne Passwörter/Secrets) | `list_helpdesk_mailboxes` | `GET /projects/:id/helpdesk/mailboxes.json` | `manage_helpdesk` (auch zum Lesen) |
| **Schreiben:** Ticket für einen Kunden anlegen (ohne Mail an den Kunden) | `create_helpdesk_ticket` | `POST /projects/:id/helpdesk/tickets.json` | Tickets hinzufügen |

Die Ticketliste der Helpdesk-API kennt **nur** `limit`/`offset`. `contact_id`, `status_id`, `assigned_to_id`,
`search` usw. werden ignoriert – deshalb hat `list_helpdesk_tickets` keine Filter.

**Mail-Protokoll** (`messages`): Richtung `in` (Kundenmail), `out` (Antwort versendet), `init` (Kontakt
zugeordnet), Betreff, Zeitpunkt, Empfänger (To/Cc/Bcc). **Kein Mailtext:** Die erste Mail ist die
Issue-Beschreibung, weitere Mails und Antworten stehen in den Kommentaren (`get_issue`).

**SLA** pro Ticket: `reaction` und `solution` mit `status` (`met`, `running`, `warning`, `breached`,
`breached_done`), Minuten, Ziel und Fälligkeit.

### Filter, die das Plugin für Issues ergänzt

Diese Filter funktionieren auf `/issues.json` und damit in `search_issues` und `search_helpdesk_tickets`:

| Filter | Bedeutung | Werte | Tool-Parameter |
|---|---|---|---|
| `helpdesk_kunde` | Kunde (Name oder Mail des Kontakts bzw. Absender der ersten Kundenmail) | `~teil` enthält, `=mail@…` exakt | `customer` |
| `helpdesk_awaiting_agent` | Kunde hat zuletzt geschrieben und wartet | `1` / `0` | `awaiting_agent` |
| `helpdesk_sla_reaction` | Zustand der Reaktionszeit | `met`, `running`, `warning`, `breached`, `breached_done` | `sla_reaction` |
| `helpdesk_sla_solution` | Zustand der Lösungszeit | wie oben | `sla_solution` |

Nach denselben Feldern lässt sich sortieren (`sort=helpdesk_sla_reaction`). In der Issue-JSON tauchen die Werte
nicht auf; dafür `get_helpdesk_ticket`.

### Wissensbasis (ab Plugin 0.23)

Beim Schließen eines Tickets extrahiert die KI ein Problem/Lösung-Paar. Freigegebene Einträge werden in einen
Vektor-Store eingebettet und für KI-Antworten und Lösungsvorschläge genutzt; eingebettet wird nur das
*Problem*. Die SQL-Tabelle ist das führende System, jede Änderung über die API bettet einen freigegebenen
Eintrag sofort neu ein bzw. entfernt jeden anderen aus dem Store.

| Information | Tool | Endpunkt | Rechte |
|---|---|---|---|
| Einträge eines Projekts, Filter Status, Freitext (Problem/Lösung), Ticket | `list_helpdesk_kb_entries` | `GET /projects/:id/helpdesk/kb_entries.json?status=…&q=…&issue_id=…` | `view_helpdesk_kb` |
| Eintrag mit Ticket, Status, `indexed`, `curated` | `get_helpdesk_kb_entry` | `GET /helpdesk/kb_entries/:id.json` | `view_helpdesk_kb` |
| **Schreiben:** Eintrag zu einem Ticket anlegen (Standard `pending`) | `create_helpdesk_kb_entry` | `POST /projects/:id/helpdesk/kb_entries.json` | `edit_helpdesk_kb` |
| **Schreiben:** Problem/Lösung korrigieren, Status `approved`/`pending` | `update_helpdesk_kb_entry` | `PUT /helpdesk/kb_entries/:id.json` | `edit_helpdesk_kb` |
| **Schreiben:** Freigeben/Ablehnen | `curate_helpdesk_kb_entry` | `POST /helpdesk/kb_entries/:id/{approve,reject}.json` | `edit_helpdesk_kb` |

Status: `pending` (wartet auf Prüfung), `approved` (eingebettet), `skipped` (KI fand keine Lösung, ohne
Statusfilter ausgeblendet), `rejected` (aus dem Store entfernt, bleibt aber, damit eine neue Extraktion ihn nicht
zurückbringt). Von Hand angelegte, geänderte oder kuratierte Einträge (`curated`) überschreibt eine neue
Extraktion nicht.

Jede Schreib-Antwort enthält `vector_sync`: `indexed` (freigegeben und durchsuchbar), `removed` (nicht
freigegeben, nicht im Store), `not_configured` (KB aus oder nicht konfiguriert), `problem_blank` (kein
Problemtext), `index_failed` / `unindex_failed` (Store nicht aktualisiert, erneut versuchen oder Index neu
aufbauen lassen).

### Was bewusst nicht geht

- **Antworten an Kunden** (`helpdesk_reply`) sind nur in der Redmine-Oberfläche möglich, nicht per API.
- **Mail beim Anlegen** (`helpdesk_init` mit `send_mail`) wird vom Server abgelehnt.
- Kommentare über `update_issue` erfassen die SLA-Erstreaktion; über die Helpdesk-Ticket-API würde das nicht
  passieren, deshalb gibt es dafür kein eigenes Tool.
- Mail-Protokoll und Kontakte sind nicht über die Redmine-Volltextsuche auffindbar.
- Statistiken und die übrigen KI-Funktionen haben keine API.
- **Wissensbasis-Einträge löschen** sowie **Index neu aufbauen** (`reindex`) und **neu extrahieren**
  (`reextract`, eine KI-Anfrage je Eintrag, überschreibt nicht kuratierte Einträge) bietet der Server nicht
  an; das bleibt dem Reiter *Wissensbasis* bzw. `manage_helpdesk_kb` vorbehalten. Lesend sind Einträge
  auch über `redmine_list("helpdesk_kb_entry", {"project_id": …})` erreichbar.

## redmine_expert_agile (Toolset `expert_agile`)

| Information | Tool | Endpunkt | Rechte |
|---|---|---|---|
| Aktueller Sprint: Issues, Story Points, erledigt, pro Person und Status | `get_sprint_overview` | `GET /issues.json?expert_agile_sprint_id=active` + `GET /issues/:id/expert_agile_data.json` je Issue | Tickets anzeigen, `view_expert_agile_board` |
| Sprints eines Projekts | `list_sprints` | `GET /projects/:id/expert_agile_sprints.json` | `manage_expert_agile_sprints` (es gibt kein reines Leserecht) |
| Sprint mit Anzahl Issues und Summe Story Points | `get_sprint` | `GET /projects/:id/expert_agile_sprints/:id.json` | wie oben |
| Story Points, Sprint, Board-Position eines Issues | `get_issue_agile_data` | `GET /issues/:id/expert_agile_data.json` | `view_expert_agile_board` |
| **Schreiben:** Sprint anlegen/ändern/aktivieren/schließen | `create_sprint`, `update_sprint` | `POST`/`PUT …/expert_agile_sprints` | `manage_expert_agile_sprints` |
| **Schreiben:** Story Points / Sprint eines Issues | `update_issue_agile_data` | `PUT /issues/:id/expert_agile_data.json` | `edit_expert_agile_board` + Tickets bearbeiten; Sprint ändern zusätzlich `manage_expert_agile_backlog` |

Die Module `expert_agile` (Board, Sprints) bzw. `expert_agile_backlog` müssen im Projekt aktiviert sein.

### Filter, die das Plugin für Issues ergänzt

| Filter | Werte | Beispiel |
|---|---|---|
| `story_points` | Zahl mit `=`, `>=`, `<=`, `><`, `*` (geschätzt), `!*` (nicht geschätzt) | `{"story_points": ">=5"}` |
| `expert_agile_sprint_id` | Sprint-Id(s) oder `active` | `{"expert_agile_sprint_id": "active"}`, `"5\|7"` |

Story Points und Sprint stehen **nicht** in der Issue-JSON, nur in `expert_agile_data.json` pro Issue. Summen
rechnet `get_sprint_overview` deshalb selbst aus (bis 200 Issues). Ist das Agile-Modul in einem Projekt aus,
ignoriert Redmine den Sprint-Filter; die Übersicht sortiert solche Issues anhand ihrer Agile-Daten aus.

**Nicht per API:** Board, Backlog, Epics, Diagramme (Burndown, Velocity). Velocity muss aus Sprints und deren
Issues berechnet werden; das Velocity-Diagramm des Plugins zählt angelegte gegen geschlossene Issues, nicht
Story Points.

**Sprint-Regeln:** Name eindeutig pro Projekt, ungeteilte Sprints eines Projekts dürfen sich zeitlich nicht
überschneiden, nur ein aktiver Sprint pro Projekt (Aktivieren setzt den bisherigen auf offen), Schließen wird
abgelehnt, solange offene Issues im Sprint sind.

## RedmineUP-Plugins (Toolset `redmineup`)

CRM-Kontakte und Deals mit Notizen, RedmineUP-Helpdesk-Tickets mit Korrespondenz, RedmineUP-Agile-Sprints und
Checklisten von Issues. Schreiben: Notiz an Kontakt/Deal, Checklisten-Punkte anlegen und abhaken.

## Rolle für den Bot-User

| Zweck | Rechte |
|---|---|
| Nur lesen, Standard | Projekt anzeigen, Tickets anzeigen, Aufwände anzeigen, Wiki anzeigen |
| + Helpdesk lesen | `view_helpdesk_info` (Kontakte, Einstellungen); Postfächer zusätzlich `manage_helpdesk`; Wissensbasis `view_helpdesk_kb` |
| + Agile lesen | `view_expert_agile_board`; Sprint-Liste zusätzlich `manage_expert_agile_sprints` |
| Schreiben | zusätzlich Tickets bearbeiten, Notizen hinzufügen, Aufwände buchen, ggf. `edit_helpdesk_kb`, `edit_expert_agile_board`, `manage_expert_agile_backlog` |

Für den Read-only-Betrieb reicht die erste Zeile plus die Plugin-Leserechte. Schreibrechte in Redmine sind dann
ohne Wirkung, weil der Server ohnehin nichts schreibt.
