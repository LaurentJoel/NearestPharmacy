// Basic smoke test for the Pharmacy App.
// Verifies the app widget tree builds without errors.

import 'package:flutter_test/flutter_test.dart';

import 'package:pharmacy_app/main.dart';

void main() {
  testWidgets('PharmacyApp builds without crashing', (
    WidgetTester tester,
  ) async {
    // Build the app and trigger a frame.
    await tester.pumpWidget(const PharmacyApp());

    // Verify that the MaterialApp and key widgets are present.
    // The app should show a loading indicator or pharmacy screen.
    expect(find.byType(PharmacyApp), findsOneWidget);
  });
}
