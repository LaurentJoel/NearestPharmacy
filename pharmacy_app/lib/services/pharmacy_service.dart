import 'package:http/http.dart' as http;
import 'dart:convert';
import '../models/pharmacy.dart';

/// Service for fetching pharmacy data from the API.
/// The base URL is injectable so the parent app can provide its own.
class PharmacyService {
  final String apiBaseUrl;

  PharmacyService({required this.apiBaseUrl});

  /// Fetch pharmacies on duty near a location.
  Future<List<Pharmacy>> fetchNearbyPharmacies({
    required double latitude,
    required double longitude,
    int radius = 10000,
  }) async {
    final response = await http
        .get(
          Uri.parse(
            '$apiBaseUrl/pharmacies/nearby?lat=$latitude&lon=$longitude&radius=$radius',
          ),
        )
        .timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      final List<dynamic> items = data['pharmacies'] ?? [];
      return items.map((item) => Pharmacy.fromJson(item)).toList();
    } else {
      throw Exception('Erreur serveur: ${response.statusCode}');
    }
  }

  /// Fetch all nearby pharmacies (regardless of duty status).
  Future<List<Pharmacy>> searchNearbyPharmacies({
    required double latitude,
    required double longitude,
    int radius = 10000,
    int limit = 50,
  }) async {
    final response = await http
        .get(
          Uri.parse(
            '$apiBaseUrl/pharmacies/search?lat=$latitude&lon=$longitude&radius=$radius&limit=$limit',
          ),
        )
        .timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      final List<dynamic> items = data['pharmacies'] ?? [];
      return items.map((item) => Pharmacy.fromJson(item)).toList();
    } else {
      throw Exception('Erreur serveur: ${response.statusCode}');
    }
  }

  /// Fetch pharmacies on duty for a specific date.
  Future<List<Pharmacy>> fetchGardes({String? date, String? ville}) async {
    final params = <String, String>{};
    if (date != null) params['date'] = date;
    if (ville != null) params['ville'] = ville;

    final uri = Uri.parse(
      '$apiBaseUrl/gardes',
    ).replace(queryParameters: params);
    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      final List<dynamic> items = data['pharmacies'] ?? [];
      return items.map((item) => Pharmacy.fromJson(item)).toList();
    } else {
      throw Exception('Erreur serveur: ${response.statusCode}');
    }
  }
}
