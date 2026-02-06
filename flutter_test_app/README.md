# Flutter Test App for Nearest Pharmacy API

A simple Flutter application to test the Nearest Pharmacy API.

## Setup

1. Make sure you have Flutter installed
2. Navigate to this directory
3. Run:
```bash
flutter create .
```
4. Replace the contents of `lib/main.dart` with the code in `main.dart.example`
5. Run the app:
```bash
flutter run
```

## Features

- Get user's GPS location
- Search for nearby pharmacies on duty
- Display results with distance
- Call pharmacy directly

## API Endpoint

The app connects to your Flask API at:
- Default: `http://10.0.2.2:5000` (Android emulator)
- iOS: `http://localhost:5000`

Update the `baseUrl` in the code for your environment.
