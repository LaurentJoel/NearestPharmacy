import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import '../models/pharmacy.dart';
import '../services/pharmacy_service.dart';
import '../widgets/pharmacy_card.dart';

/// Embeddable pharmacy screen widget.
///
/// This is the main entry point for integrating the pharmacy feature
/// into a parent app. It can be used as a full screen or nested inside
/// a tab/navigation stack.
///
/// Usage in parent app:
/// ```dart
/// Navigator.push(context, MaterialPageRoute(
///   builder: (_) => PharmacyScreen(apiBaseUrl: 'https://myapp.com/pharmacy/api'),
/// ));
/// ```
///
/// Or with pre-fetched position:
/// ```dart
/// PharmacyScreen(
///   apiBaseUrl: 'https://myapp.com/pharmacy/api',
///   initialPosition: myAlreadyFetchedPosition,
/// )
/// ```
class PharmacyScreen extends StatefulWidget {
  /// Base URL for the pharmacy API.
  /// Example: 'http://10.0.2.2:5000/api' or 'https://myapp.com/pharmacy/api'
  final String apiBaseUrl;

  /// Optional pre-fetched GPS position from the parent app.
  /// If provided, the screen will not request GPS permission or fetch location.
  final Position? initialPosition;

  /// Whether to show the header with title and coordinates.
  /// Set to false if the parent app provides its own app bar.
  final bool showHeader;

  /// Optional callback when a pharmacy is tapped (for custom handling).
  /// If null, the default detail bottom sheet is shown.
  final void Function(Pharmacy pharmacy)? onPharmacyTap;

  const PharmacyScreen({
    super.key,
    required this.apiBaseUrl,
    this.initialPosition,
    this.showHeader = true,
    this.onPharmacyTap,
  });

  @override
  State<PharmacyScreen> createState() => _PharmacyScreenState();
}

class _PharmacyScreenState extends State<PharmacyScreen>
    with SingleTickerProviderStateMixin {
  bool _isLoading = false;
  bool _hasError = false;
  String _errorMessage = '';
  List<Pharmacy> _pharmacies = [];
  Position? _currentPosition;
  late AnimationController _animationController;
  late PharmacyService _service;
  int _selectedRadius = 10000;

  @override
  void initState() {
    super.initState();
    _service = PharmacyService(apiBaseUrl: widget.apiBaseUrl);
    _animationController = AnimationController(
      duration: const Duration(seconds: 1),
      vsync: this,
    )..repeat();

    if (widget.initialPosition != null) {
      _currentPosition = widget.initialPosition;
      _fetchNearbyPharmacies();
    } else {
      _getCurrentLocation();
    }
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  Future<void> _getCurrentLocation() async {
    setState(() {
      _isLoading = true;
      _hasError = false;
    });

    try {
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          throw Exception('Permission de localisation refusée');
        }
      }

      if (permission == LocationPermission.deniedForever) {
        throw Exception('Permission de localisation refusée définitivement');
      }

      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      setState(() {
        _currentPosition = position;
      });

      await _fetchNearbyPharmacies();
    } catch (e) {
      setState(() {
        _hasError = true;
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _fetchNearbyPharmacies() async {
    if (_currentPosition == null) return;

    setState(() {
      _isLoading = true;
      _hasError = false;
    });

    try {
      final pharmacies = await _service.fetchNearbyPharmacies(
        latitude: _currentPosition!.latitude,
        longitude: _currentPosition!.longitude,
        radius: _selectedRadius,
      );
      setState(() {
        _pharmacies = pharmacies;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _hasError = true;
        _errorMessage = 'Impossible de charger les pharmacies: $e';
        _isLoading = false;
      });
    }
  }

  void _showPharmacyDetails(Pharmacy pharmacy) {
    if (widget.onPharmacyTap != null) {
      widget.onPharmacyTap!(pharmacy);
      return;
    }

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => PharmacyDetailSheet(pharmacy: pharmacy),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Theme.of(context).colorScheme.primary,
            Theme.of(context).colorScheme.primaryContainer,
          ],
        ),
      ),
      child: SafeArea(
        child: Column(
          children: [
            if (widget.showHeader) _buildHeader(),
            _buildRadiusSelector(),
            Expanded(child: _buildContent()),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Icon(
                  Icons.local_pharmacy,
                  size: 32,
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: 12),
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Pharmacies',
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  Text(
                    'de Garde',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w300,
                      color: Colors.white70,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_currentPosition != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.location_on, color: Colors.white, size: 16),
                  const SizedBox(width: 4),
                  Text(
                    '${_currentPosition!.latitude.toStringAsFixed(4)}, ${_currentPosition!.longitude.toStringAsFixed(4)}',
                    style: const TextStyle(color: Colors.white, fontSize: 12),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildRadiusSelector() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _radiusChip(5000, '5 km'),
          _radiusChip(10000, '10 km'),
          _radiusChip(20000, '20 km'),
        ],
      ),
    );
  }

  Widget _radiusChip(int radius, String label) {
    final isSelected = _selectedRadius == radius;
    return GestureDetector(
      onTap: () {
        setState(() => _selectedRadius = radius);
        _fetchNearbyPharmacies();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? Colors.white : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: TextStyle(
            color:
                isSelected
                    ? Theme.of(context).colorScheme.primary
                    : Colors.white,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }

  Widget _buildContent() {
    if (_isLoading) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            RotationTransition(
              turns: _animationController,
              child: const Icon(
                Icons.local_pharmacy,
                size: 60,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'Recherche en cours...',
              style: TextStyle(color: Colors.white, fontSize: 18),
            ),
          ],
        ),
      );
    }

    if (_hasError) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 64, color: Colors.white70),
              const SizedBox(height: 16),
              Text(
                _errorMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white, fontSize: 16),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: _getCurrentLocation,
                icon: const Icon(Icons.refresh),
                label: const Text('Réessayer'),
              ),
            ],
          ),
        ),
      );
    }

    if (_pharmacies.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off, size: 64, color: Colors.white70),
            SizedBox(height: 16),
            Text(
              'Aucune pharmacie de garde\ntrouvée dans cette zone',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white, fontSize: 18),
            ),
          ],
        ),
      );
    }

    return Container(
      margin: const EdgeInsets.only(top: 16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(30),
          topRight: Radius.circular(30),
        ),
      ),
      child: Column(
        children: [
          const SizedBox(height: 16),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.only(bottom: 80),
              itemCount: _pharmacies.length,
              itemBuilder: (context, index) {
                return PharmacyCard(
                  pharmacy: _pharmacies[index],
                  index: index,
                  onTap: () => _showPharmacyDetails(_pharmacies[index]),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
