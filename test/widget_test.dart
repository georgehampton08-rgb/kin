import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:kin/main.dart';
import 'package:kin/providers/location_provider.dart';

void main() {
  testWidgets('Renders app and shows fetching text initially', (WidgetTester tester) async {
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => LocationProvider()),
        ],
        child: const KinApp(),
      ),
    );

    expect(find.text('Privacy First'), findsOneWidget);
  });
}
