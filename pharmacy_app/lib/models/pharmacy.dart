/// Pharmacy data model.
/// Used across the pharmacy feature module.
class Pharmacy {
  final int? id;
  final String nom;
  final String? adresse;
  final String? telephone;
  final String? ville;
  final double? latitude;
  final double? longitude;
  final double? distanceM;
  final String? type;
  final String? nomScrape;
  final String? quarterScrape;

  Pharmacy({
    this.id,
    required this.nom,
    this.adresse,
    this.telephone,
    this.ville,
    this.latitude,
    this.longitude,
    this.distanceM,
    this.type,
    this.nomScrape,
    this.quarterScrape,
  });

  factory Pharmacy.fromJson(Map<String, dynamic> json) {
    return Pharmacy(
      id: json['id'] as int?,
      nom: json['nom'] ?? 'Pharmacie',
      adresse: json['adresse'] as String?,
      telephone: json['telephone'] as String?,
      ville: json['ville'] as String?,
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      distanceM: (json['distance_m'] as num?)?.toDouble(),
      type: json['type'] as String?,
      nomScrape: json['nom_scrape'] as String?,
      quarterScrape: json['quarter_scrape'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'nom': nom,
      'adresse': adresse,
      'telephone': telephone,
      'ville': ville,
      'latitude': latitude,
      'longitude': longitude,
      'distance_m': distanceM,
      'type': type,
      'nom_scrape': nomScrape,
      'quarter_scrape': quarterScrape,
    };
  }

  /// Distance as human-readable string.
  String get distanceText {
    if (distanceM == null) return '?';
    if (distanceM! < 1000) return '${distanceM!.toInt()} m';
    return '${(distanceM! / 1000).toStringAsFixed(1)} km';
  }

  /// Distance in km as string (for detail view).
  String get distanceKmText {
    if (distanceM == null) return 'Inconnue';
    return '${(distanceM! / 1000).toStringAsFixed(2)} km';
  }

  bool get hasLocation => latitude != null && longitude != null;
  bool get hasPhone => telephone != null && telephone!.isNotEmpty;
}
