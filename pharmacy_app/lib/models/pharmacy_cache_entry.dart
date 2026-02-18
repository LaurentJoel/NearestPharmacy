import 'package:hive/hive.dart';

/// Hive adapter for Pharmacy model.
/// Stores pharmacy data locally for offline availability.
///
/// TypeId 0 is reserved for PharmacyCacheEntry.
class PharmacyCacheEntry extends HiveObject {
  @HiveField(0)
  final int? id;

  @HiveField(1)
  final String nom;

  @HiveField(2)
  final String? adresse;

  @HiveField(3)
  final String? telephone;

  @HiveField(4)
  final String? ville;

  @HiveField(5)
  final double? latitude;

  @HiveField(6)
  final double? longitude;

  @HiveField(7)
  final double? distanceM;

  @HiveField(8)
  final String? type;

  @HiveField(9)
  final String? nomScrape;

  @HiveField(10)
  final String? quarterScrape;

  PharmacyCacheEntry({
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
}

/// Manual Hive adapter for PharmacyCacheEntry.
/// We write this manually to avoid hive_generator dependency.
class PharmacyCacheEntryAdapter extends TypeAdapter<PharmacyCacheEntry> {
  @override
  final int typeId = 0;

  @override
  PharmacyCacheEntry read(BinaryReader reader) {
    final numFields = reader.readByte();
    final fields = <int, dynamic>{};
    for (var i = 0; i < numFields; i++) {
      fields[reader.readByte()] = reader.read();
    }
    return PharmacyCacheEntry(
      id: fields[0] as int?,
      nom: fields[1] as String? ?? 'Pharmacie',
      adresse: fields[2] as String?,
      telephone: fields[3] as String?,
      ville: fields[4] as String?,
      latitude: fields[5] as double?,
      longitude: fields[6] as double?,
      distanceM: fields[7] as double?,
      type: fields[8] as String?,
      nomScrape: fields[9] as String?,
      quarterScrape: fields[10] as String?,
    );
  }

  @override
  void write(BinaryWriter writer, PharmacyCacheEntry obj) {
    writer
      ..writeByte(11) // number of fields
      ..writeByte(0)
      ..write(obj.id)
      ..writeByte(1)
      ..write(obj.nom)
      ..writeByte(2)
      ..write(obj.adresse)
      ..writeByte(3)
      ..write(obj.telephone)
      ..writeByte(4)
      ..write(obj.ville)
      ..writeByte(5)
      ..write(obj.latitude)
      ..writeByte(6)
      ..write(obj.longitude)
      ..writeByte(7)
      ..write(obj.distanceM)
      ..writeByte(8)
      ..write(obj.type)
      ..writeByte(9)
      ..write(obj.nomScrape)
      ..writeByte(10)
      ..write(obj.quarterScrape);
  }
}
