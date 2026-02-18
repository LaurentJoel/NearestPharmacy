import 'package:hive_flutter/hive_flutter.dart';
import '../models/pharmacy.dart';
import '../models/pharmacy_cache_entry.dart';

/// Local cache service using Hive for offline pharmacy data.
///
/// Caches API responses on disk so the app works even when
/// the network is unstable (common in Cameroon).
///
/// Cache strategy:
///   - Nearby pharmacies: cached per rounded location, TTL = 15 min
///   - Gardes list: cached per date+city, TTL = 30 min
///   - All pharmacies: cached per city, TTL = 24 hours
///
/// Usage:
///   final cache = PharmacyCacheService();
///   await cache.init();
///
///   // Store
///   await cache.cacheNearbyPharmacies(lat, lon, pharmacies);
///
///   // Retrieve (returns null if expired or not found)
///   final cached = cache.getCachedNearbyPharmacies(lat, lon);
class PharmacyCacheService {
  static const String _nearbyBoxName = 'nearby_pharmacies';
  static const String _metaBoxName = 'cache_meta';

  // TTL durations
  static const Duration nearbyTTL = Duration(minutes: 15);
  static const Duration gardesTTL = Duration(minutes: 30);
  static const Duration allPharmaciesTTL = Duration(hours: 24);

  late Box<List> _nearbyBox;
  late Box _metaBox;

  bool _initialized = false;

  /// Initialize Hive boxes. Must be called once at app start.
  Future<void> init() async {
    if (_initialized) return;

    // Register adapter if not already registered
    if (!Hive.isAdapterRegistered(0)) {
      Hive.registerAdapter(PharmacyCacheEntryAdapter());
    }

    _nearbyBox = await Hive.openBox<List>(_nearbyBoxName);
    _metaBox = await Hive.openBox(_metaBoxName);
    _initialized = true;
  }

  // ──────────────────────────────────────────────
  // Nearby pharmacies (on duty)
  // ──────────────────────────────────────────────

  /// Cache key for nearby query (rounds to ~100m precision).
  String _nearbyKey(double lat, double lon, int radius) {
    final latKey = lat.toStringAsFixed(3);
    final lonKey = lon.toStringAsFixed(3);
    return 'nearby:$latKey:$lonKey:$radius';
  }

  /// Store nearby pharmacies in local cache.
  Future<void> cacheNearbyPharmacies(
    double lat,
    double lon,
    int radius,
    List<Pharmacy> pharmacies,
  ) async {
    if (!_initialized) return;

    final key = _nearbyKey(lat, lon, radius);
    final entries =
        pharmacies
            .map(
              (p) => PharmacyCacheEntry(
                id: p.id,
                nom: p.nom,
                adresse: p.adresse,
                telephone: p.telephone,
                ville: p.ville,
                latitude: p.latitude,
                longitude: p.longitude,
                distanceM: p.distanceM,
                type: p.type,
                nomScrape: p.nomScrape,
                quarterScrape: p.quarterScrape,
              ),
            )
            .toList();

    await _nearbyBox.put(key, entries);
    await _metaBox.put('ts:$key', DateTime.now().millisecondsSinceEpoch);
  }

  /// Get cached nearby pharmacies. Returns null if not found or expired.
  List<Pharmacy>? getCachedNearbyPharmacies(
    double lat,
    double lon,
    int radius,
  ) {
    if (!_initialized) return null;

    final key = _nearbyKey(lat, lon, radius);
    final timestamp = _metaBox.get('ts:$key') as int?;

    if (timestamp == null) return null;

    final cachedAt = DateTime.fromMillisecondsSinceEpoch(timestamp);
    if (DateTime.now().difference(cachedAt) > nearbyTTL) {
      // Expired — clean up
      _nearbyBox.delete(key);
      _metaBox.delete('ts:$key');
      return null;
    }

    final entries = _nearbyBox.get(key);
    if (entries == null) return null;

    return entries
        .cast<PharmacyCacheEntry>()
        .map(
          (e) => Pharmacy(
            id: e.id,
            nom: e.nom,
            adresse: e.adresse,
            telephone: e.telephone,
            ville: e.ville,
            latitude: e.latitude,
            longitude: e.longitude,
            distanceM: e.distanceM,
            type: e.type,
            nomScrape: e.nomScrape,
            quarterScrape: e.quarterScrape,
          ),
        )
        .toList();
  }

  // ──────────────────────────────────────────────
  // Gardes (on-duty list by date)
  // ──────────────────────────────────────────────

  String _gardesKey(String? date, String? ville) {
    return 'gardes:${date ?? 'today'}:${ville ?? 'all'}';
  }

  /// Store gardes data in local cache.
  Future<void> cacheGardes(
    String? date,
    String? ville,
    List<Pharmacy> pharmacies,
  ) async {
    if (!_initialized) return;

    final key = _gardesKey(date, ville);
    final entries =
        pharmacies
            .map(
              (p) => PharmacyCacheEntry(
                id: p.id,
                nom: p.nom,
                adresse: p.adresse,
                telephone: p.telephone,
                ville: p.ville,
                latitude: p.latitude,
                longitude: p.longitude,
                distanceM: p.distanceM,
                type: p.type,
                nomScrape: p.nomScrape,
                quarterScrape: p.quarterScrape,
              ),
            )
            .toList();

    await _nearbyBox.put(key, entries);
    await _metaBox.put('ts:$key', DateTime.now().millisecondsSinceEpoch);
  }

  /// Get cached gardes data. Returns null if not found or expired.
  List<Pharmacy>? getCachedGardes(String? date, String? ville) {
    if (!_initialized) return null;

    final key = _gardesKey(date, ville);
    final timestamp = _metaBox.get('ts:$key') as int?;

    if (timestamp == null) return null;

    final cachedAt = DateTime.fromMillisecondsSinceEpoch(timestamp);
    if (DateTime.now().difference(cachedAt) > gardesTTL) {
      _nearbyBox.delete(key);
      _metaBox.delete('ts:$key');
      return null;
    }

    final entries = _nearbyBox.get(key);
    if (entries == null) return null;

    return entries
        .cast<PharmacyCacheEntry>()
        .map(
          (e) => Pharmacy(
            id: e.id,
            nom: e.nom,
            adresse: e.adresse,
            telephone: e.telephone,
            ville: e.ville,
            latitude: e.latitude,
            longitude: e.longitude,
            distanceM: e.distanceM,
            type: e.type,
            nomScrape: e.nomScrape,
            quarterScrape: e.quarterScrape,
          ),
        )
        .toList();
  }

  // ──────────────────────────────────────────────
  // Utilities
  // ──────────────────────────────────────────────

  /// Clear all cached data.
  Future<void> clearAll() async {
    if (!_initialized) return;
    await _nearbyBox.clear();
    await _metaBox.clear();
  }

  /// Get cache statistics (for debugging / health check).
  Map<String, dynamic> getStats() {
    if (!_initialized) return {'initialized': false};
    return {
      'initialized': true,
      'entries': _nearbyBox.length,
      'meta_entries': _metaBox.length,
    };
  }
}
