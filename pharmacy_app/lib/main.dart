import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'screens/pharmacy_screen.dart';

/// Standalone entry point for the Pharmacy app.
/// When integrated into a parent app, use PharmacyScreen directly instead.
///
/// Integration example (in parent app):
/// ```dart
/// import 'package:pharmacy_app/pharmacy_feature.dart';
///
/// // Initialize Hive before using pharmacy feature:
/// await Hive.initFlutter();
///
/// // As a route:
/// Navigator.push(context, MaterialPageRoute(
///   builder: (_) => Scaffold(
///     appBar: AppBar(title: Text('Pharmacies de Garde')),
///     body: PharmacyScreen(
///       apiBaseUrl: 'https://yourapp.com/pharmacy/api',
///       showHeader: false, // parent provides AppBar
///     ),
///   ),
/// ));
///
/// // Or with pre-fetched position:
/// PharmacyScreen(
///   apiBaseUrl: 'https://yourapp.com/pharmacy/api',
///   initialPosition: alreadyFetchedPosition,
/// )
/// ```
void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Hive for local caching (offline support)
  await Hive.initFlutter();

  runApp(const PharmacyApp());
}

class PharmacyApp extends StatelessWidget {
  const PharmacyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Pharmacies de Garde',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF00C853),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
        fontFamily: 'Roboto',
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF00C853),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        fontFamily: 'Roboto',
      ),
      themeMode: ThemeMode.system,
      home: Scaffold(
        body: const PharmacyScreen(
          // Uses ADB reverse port forwarding (adb reverse tcp:5000 tcp:5000)
          // This is more reliable than 10.0.2.2 which can break after emulator sleep
          apiBaseUrl:
              'http://localhost:5000/api', // Android emulator via ADB reverse
          // For real phone: 'http://YOUR_COMPUTER_IP:5000/api'
        ),
        floatingActionButton: Builder(
          builder:
              (context) => FloatingActionButton.extended(
                onPressed: () {
                  // Re-navigate to refresh (standalone mode convenience)
                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(builder: (_) => const PharmacyApp()),
                  );
                },
                icon: const Icon(Icons.refresh),
                label: const Text('Actualiser'),
                backgroundColor: Theme.of(context).colorScheme.primaryContainer,
              ),
        ),
      ),
    );
  }
}
