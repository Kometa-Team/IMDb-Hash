# IMDb Hash

Last generated at: May 29, 2026 20:07 UTC

Validates the persisted-query hashes used by IMDb's GraphQL API for:

- Advanced title searches
- IMDb lists
- IMDb watchlists

The scheduled GitHub Actions workflow runs every six hours. It validates the
values stored in `HASH`, `LIST_HASH`, and `WATCHLIST_HASH` directly against
IMDb's GraphQL endpoint. The job exits with an error if a hash is invalid or
cannot be verified.

## Running locally

Python 3.11 or newer is required.

```shell
python -m pip install -r requirements.txt
python check-imdb-hash.py
```

To use a different title-search keyword:

```shell
python check-imdb-hash.py --keyword "The Godfather"
```

To regenerate invalid hashes using the browser workflow:

```shell
python check-imdb-hash.py --refresh
```

IMDb may present an interactive human-verification check during a refresh.
Run refreshes locally so that check can be completed in the visible browser.

## Discord notifications

Failed GitHub Actions runs send a Discord notification through the
`Kometa-Team/discord-notifications` action. Configure the repository secret
`BUILD_WEBHOOK` with the Discord webhook ID and token expected by that action.
The workflow's repository variables control the notification text, appearance,
and role mention.

Never commit a Discord webhook URL or token to this repository.
