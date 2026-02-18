import 'package:http/http.dart' as http;
import 'dart:convert';
import '../models/pharmacy.dart';
import 'pharmacy_cache_service.dart';

/// Service for fetching pharmacy data from the API.
/// Integrated with Hive-based local caching for offline resilience.
///
/// Strategy:
///   1. Try API first (online)
///   2. On success → return data + cache it locally
///   3. On failure (network error) → return cached data if available
///   4. If no cache → throw the original error
class PharmacyService {
  final String apiBaseUrl;
  final PharmacyCacheService _cache = PharmacyCacheService();
  bool _cacheReady = false;

  PharmacyService({required this.apiBaseUrl}) {
    _initCache();
  }

  Future<void> _initCache() async {
    try {
      await _cache.init();
      _cacheReady = true;
    } catch (e) {
      // Cache init failure is not fatal — just continue without cache
      _cacheReady = false;
    }
  }

  /// Fetch pharmacies on duty near a location.
  /// Falls back to Hive cache if the network request fails.
  Future<List<Pharmacy>> fetchNearbyPharmacies({
    required double latitude,
    required double longitude,
    int radius = 10000,
  }) async {
    try {
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
        final pharmacies =
            items.map((item) => Pharmacy.fromJson(item)).toList();

        // Cache the fresh result
        if (_cacheReady) {
          await _cache.cacheNearbyPharmacies(
            latitude,
            longitude,
            radius,
            pharmacies,
          );
        }

        return pharmacies;
      } else {
        throw Exception('Erreur serveur: ${response.statusCode}');
      }
    } catch (e) {
      // Network failed — try local cache
      if (_cacheReady) {
        final cached = _cache.getCachedNearbyPharmacies(
          latitude,
          longitude,
          radius,
        );
        if (cached != null && cached.isNotEmpty) {
          return cached;
        }
      }
      rethrow; // No cache available — propagate error to UI
    }
  }

  /// Fetch all nearby pharmacies (regardless of duty status).
  Future<List<Pharmacy>> searchNearbyPharmacies({
    required double latitude,
    required double longitude,
    int radius = 10000,
    int limit = 50,
  }) async {
    try {
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
    } catch (e) {
      rethrow;
    }
  }

  /// Fetch pharmacies on duty for a specific date.
  /// Falls back to Hive cache if the network request fails.
  Future<List<Pharmacy>> fetchGardes({String? date, String? ville}) async {
    try {
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
        final pharmacies =
            items.map((item) => Pharmacy.fromJson(item)).toList();

        // Cache the fresh result
        if (_cacheReady) {
          await _cache.cacheGardes(date, ville, pharmacies);
        }

        return pharmacies;
      } else {
        throw Exception('Erreur serveur: ${response.statusCode}');
      }
    } catch (e) {
      // Network failed — try local cache
      if (_cacheReady) {
        final cached = _cache.getCachedGardes(date, ville);
        if (cached != null && cached.isNotEmpty) {
          return cached;
        }
      }
      rethrow;
    }
  }

  /// Clear local cache (useful for force-refresh).
  Future<void> clearCache() async {
    if (_cacheReady) {
      await _cache.clearAll();
    }
  }

  /// Get cache statistics.
  Map<String, dynamic> getCacheStats() {
    return _cache.getStats();
  }
}
