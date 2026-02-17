import 'package:flutter/material.dart';
import 'screens/pharmacy_screen.dart';

/// Standalone entry point for the Pharmacy app.
/// When integrated into a parent app, use PharmacyScreen directly instead.
///
/// Integration example (in parent app):
/// ```dart
/// import 'package:pharmacy_app/pharmacy_feature.dart';
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
void main() {
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
          // TODO: Change this to your server's address
          apiBaseUrl: 'http://10.0.2.2:5000/api', // Android emulator
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
