import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/pharmacy.dart';

/// A card widget that displays a single pharmacy in a list.
/// Reusable by any parent app.
class PharmacyCard extends StatelessWidget {
  final Pharmacy pharmacy;
  final int index;
  final VoidCallback? onTap;

  const PharmacyCard({
    super.key,
    required this.pharmacy,
    required this.index,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        Theme.of(context).colorScheme.primary,
                        Theme.of(context).colorScheme.secondary,
                      ],
                    ),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Center(
                    child: Text(
                      '${index + 1}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                        fontSize: 18,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        pharmacy.nom,
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(
                            Icons.location_on,
                            size: 14,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            pharmacy.ville ?? '',
                            style: TextStyle(
                              color:
                                  Theme.of(
                                    context,
                                  ).colorScheme.onSurfaceVariant,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    if (pharmacy.distanceText != '?')
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.primaryContainer,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          pharmacy.distanceText,
                          style: TextStyle(
                            color:
                                Theme.of(
                                  context,
                                ).colorScheme.onPrimaryContainer,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    const SizedBox(height: 8),
                    Icon(
                      Icons.chevron_right,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Bottom sheet with pharmacy details, directions, and call buttons.
class PharmacyDetailSheet extends StatelessWidget {
  final Pharmacy pharmacy;

  const PharmacyDetailSheet({super.key, required this.pharmacy});

  void _openMaps(double lat, double lon) async {
    final url = Uri.parse(
      'https://www.google.com/maps/dir/?api=1&destination=$lat,$lon&travelmode=driving',
    );
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    }
  }

  void _callPharmacy(String phone) async {
    if (phone.isEmpty) return;
    final cleanPhone = phone.replaceAll(' ', '');
    final url = Uri.parse('tel:$cleanPhone');
    if (await canLaunchUrl(url)) {
      await launchUrl(url);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.5,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(30),
          topRight: Radius.circular(30),
        ),
      ),
      child: Column(
        children: [
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: Colors.grey[300],
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [
                              Theme.of(context).colorScheme.primary,
                              Theme.of(context).colorScheme.secondary,
                            ],
                          ),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: const Icon(
                          Icons.local_pharmacy,
                          color: Colors.white,
                          size: 32,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              pharmacy.nom,
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 20,
                              ),
                            ),
                            Text(
                              pharmacy.ville ?? '',
                              style: TextStyle(
                                color:
                                    Theme.of(
                                      context,
                                    ).colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  if (pharmacy.distanceM != null)
                    _detailRow(
                      context,
                      Icons.straighten,
                      'Distance',
                      pharmacy.distanceKmText,
                    ),
                  if (pharmacy.adresse?.isNotEmpty ?? false)
                    _detailRow(
                      context,
                      Icons.home,
                      'Adresse',
                      pharmacy.adresse!,
                    ),
                  if (pharmacy.hasPhone)
                    _detailRow(
                      context,
                      Icons.phone,
                      'Téléphone',
                      pharmacy.telephone!,
                    ),
                  const Spacer(),
                  Row(
                    children: [
                      if (pharmacy.hasLocation)
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed:
                                () => _openMaps(
                                  pharmacy.latitude!,
                                  pharmacy.longitude!,
                                ),
                            icon: const Icon(Icons.directions),
                            label: const Text('Itinéraire'),
                            style: ElevatedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(vertical: 16),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                              ),
                            ),
                          ),
                        ),
                      if (pharmacy.hasPhone) ...[
                        if (pharmacy.hasLocation) const SizedBox(width: 12),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () => _callPharmacy(pharmacy.telephone!),
                            icon: const Icon(Icons.phone),
                            label: const Text('Appeler'),
                            style: OutlinedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(vertical: 16),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _detailRow(
    BuildContext context,
    IconData icon,
    String label,
    String value,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(icon, color: Theme.of(context).colorScheme.primary, size: 20),
          const SizedBox(width: 12),
          Text('$label: ', style: const TextStyle(fontWeight: FontWeight.w500)),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
