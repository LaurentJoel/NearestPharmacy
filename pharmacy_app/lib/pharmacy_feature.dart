/// Pharmacy Feature Module - Public API
/// ======================================
/// Export this file from the parent app to access all pharmacy feature components.
///
/// Usage in parent app:
/// ```dart
/// import 'package:pharmacy_app/pharmacy_feature.dart';
///
/// // Initialize Hive before using pharmacy feature (if parent hasn't already):
/// await Hive.initFlutter();
///
/// // Navigate to pharmacy screen
/// Navigator.push(context, MaterialPageRoute(
///   builder: (_) => PharmacyScreen(apiBaseUrl: 'https://myapp.com/pharmacy/api'),
/// ));
///
/// // Or use individual components
/// PharmacyService service = PharmacyService(apiBaseUrl: '...');
/// List<Pharmacy> pharmacies = await service.fetchNearbyPharmacies(...);
/// ```
library pharmacy_feature;

// Models
export 'models/pharmacy.dart';

// Services
export 'services/pharmacy_service.dart';
export 'services/pharmacy_cache_service.dart';

// Screens
export 'screens/pharmacy_screen.dart';

// Widgets
export 'widgets/pharmacy_card.dart';

// Re-export Hive init for parent app convenience
export 'package:hive_flutter/hive_flutter.dart' show Hive;
