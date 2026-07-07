# BoneCast 🦴📡

**Twitch w Trybie Gry Steam** — wtyczka [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) dla Steam Deck / Bazzite / SteamOS.

🌍 **Języki:** [English](../README.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Italiano](README.it.md) · [Português](README.pt.md) · [Nederlands](README.nl.md) · **Polski** · [Русский](README.ru.md)

> Część zestawu wtyczek Necrosiak, obok
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) i BC250-Toolkit.
> Interfejs wtyczki jest przetłumaczony na 9 języków i automatycznie podąża za językiem SteamOS.

---

## Co potrafi

BoneCast umieszcza wszystko, czego potrzebujesz do transmisji na **Twitcha**, bezpośrednio w **Menu Szybkiego Dostępu** Steam — bez pulpitu, bez klawiatury, w pełni pod pada od logowania aż po wejście na żywo.

- **Jedno logowanie do Twitcha** *(kod urządzenia — przyjazny padowi)*: wpisujesz krótki kod na `twitch.tv/activate`, a BoneCast **automatycznie pobiera klucz transmisji**. Koniec z kopiowaniem i wklejaniem.
- **Wejdź na żywo z QAM** — jeden przycisk uruchamia i zatrzymuje strumień RTMP. Podczas transmisji wyświetla się plakietka **● NA ŻYWO**.
- **Edytowalny tytuł transmisji** — ustawiany z wtyczki, zmienny **nawet na żywo**.
- **Automatyczna kategoria gry** — odczytana z uruchomionej gry Steam (działa też ze skrótami spoza Steam) i aktualizowana na bieżąco. Wraca do *Just Chatting*, gdy gra nie ma odpowiedniej kategorii na Twitchu.
- **Przezroczysta nakładka czatu** — czat Twitcha tylko do odczytu rysowany **nad grą** w Trybie Gry (płaszczyzna external-overlay gamescope), z natywnymi emotkami + **BTTV / 7TV / FFZ**. Przesuwalny i stylizowalny.
- **Wyciszenie mikrofonu na żywo** — wycisz mikrofon **na transmisji** jednym dotknięciem, bez zatrzymywania nadawania (i bez wyciszania połączenia Discord).
- **Ustawienia transmisji per konto** — rozdzielczość, fps, przepływność wideo/audio, odstęp klatek kluczowych oraz **automatycznie wykrywany koder** (NVENC ▸ VAAPI ▸ programowy x264). Oferowane są tylko kodery, które faktycznie działają na twoim sprzęcie.
- **Most audio Discord** *(gdy zainstalowany jest [Steamcord](https://github.com/Necrosiak/Steamcord))*: opcjonalny przełącznik miksuje twój **głos z Discorda** do transmisji, aby twoja ekipa była słyszana przez widzów — a ty nadal słyszysz ich normalnie.

---

## Jak to działa

Twitch nie ma API do wysyłania wideo, więc wejście na żywo zawsze oznacza **wypychanie RTMP** w tle. BoneCast zajmuje się tym za ciebie:

1. **Przepływ OAuth z kodem urządzenia** loguje cię do Twitcha i pobiera twój klucz transmisji, tytuł i kategorię przez API Helix — nigdy nie dotykasz klucza.
2. Klatka gry jest przechwytywana z **gamescope** do urządzenia pętli zwrotnej `v4l2`, a **ffmpeg** koduje ją (sprzętowo, jeśli dostępne, w przeciwnym razie programowo `libx264`) i wypycha do `rtmp://…/<twój-klucz>`.
3. **Nakładka czatu** to przezroczysta powierzchnia WebKit awansowana na płaszczyznę external-overlay gamescope, która anonimowo czyta IRC Twitcha i renderuje emotki.

Wszystko sterowane jest z QAM i przetrwa restarty.

---

## Instalacja

1. Zainstaluj [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Pobierz najnowszy `BoneCast.zip` ze strony [Releases](https://github.com/Necrosiak/BoneCast/releases) lub zainstaluj ze sklepu Decky, gdy będzie dostępny.
3. Otwórz **Menu Szybkiego Dostępu → BoneCast**, zaloguj się do Twitcha i wejdź na żywo.

BoneCast **aktualizuje się automatycznie** z wydań GitHub (przełączane w sekcji *Aktualizacje* wtyczki).

---

## Podziękowania

Stworzone i utrzymywane przez **Necrosiak**. Część zestawu wtyczek Necrosiak dla Trybu Gry Steam.
