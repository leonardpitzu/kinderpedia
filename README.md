# Kinderpedia for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration that brings your child's [Kinderpedia](https://www.kinderpedia.com/) kindergarten data into your smart home dashboard — daily meals, nap times, check-ins, and newsfeed activity, all at a glance.

## Features

### Calendar

A calendar entity (`<name> school`) shows the full weekly timeline your kindergarten reports through Kinderpedia:

- **School event** — a timed event starting at the check-in time and ending at 18:00. The description shows each meal on its own line with an icon and consumption percentage:
  ```
  🥣 Breakfast (100%): Tartine cu hummus, ardei și ceai
  🍽️ Lunch (75%): Supă cremă de morcov, Papricaș de pui
  🍪 Snack: Biscuiți cu ovăz
  ```
- **Nap event** — a separate timed event using the actual nap start/end times reported by the teacher.

The calendar entity also exposes **detailed attributes** for the most recent school day (or today, if available): `checkin`, `nap`, `nap_duration`, `breakfast_items`, `breakfast_percent`, `breakfast_kcal`, `lunch_items`, `lunch_percent`, `lunch_kcal`, `snack_items`, and more. These are ready to use in template cards or automations.

### Sensors

| Sensor | Description |
|---|---|
| **Child info** | Name, birth date, gender, kindergarten name |
| **Breakfast week** | Weekly breakfast consumption percentages (Mon–Fri) for charting |
| **Lunch week** | Weekly lunch consumption percentages (Mon–Fri) for charting |
| **Nap week** | Weekly nap durations in minutes (Mon–Fri) for charting |
| **Newsfeed** | Latest school newsfeed post (icon: `mdi:newspaper-variant-outline`). Recent entries available as an attribute |

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations** → **⋮** → **Custom repositories**.
3. Add `https://github.com/leonardpitzu/kinderpedia` as an **Integration**.
4. Search for **Kinderpedia** and install it.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/kinderpedia` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Kinderpedia**.
3. Enter your Kinderpedia email and password.
4. The integration will discover all children linked to your account and create entities automatically.

Data is polled every 15 minutes.

## Dashboard ideas

- Use the **calendar card** for a quick daily glance — meal icons, percentages, and nap times are visible at a glance.
- Use the **week sensors** (`breakfast_week`, `lunch_week`, `nap_week`) with an [ApexCharts card](https://github.com/RomRider/apexcharts-card) to visualise weekly trends.
- Use the calendar entity's **extra attributes** in template cards for a detailed breakdown of today's meals.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
