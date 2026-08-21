package com.frost.bluetoothguard;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import org.junit.Test;

public class WarningEngineTest {
    @Test
    public void unknownConnectionIsCritical() {
        List<WarningEngine.Warning> warnings = WarningEngine.onConnect(
                "aa:bb:cc:dd:ee:ff", "Unknown", false,
                Collections.singletonList(1L), null, 1, 3);
        assertEquals("UNKNOWN_CONNECTED", warnings.get(0).code);
        assertEquals(WarningEngine.Severity.CRITICAL, warnings.get(0).severity);
    }

    @Test
    public void trustedConnectionIsInformational() {
        List<WarningEngine.Warning> warnings = WarningEngine.onConnect(
                "AA:BB:CC:DD:EE:FF", "Headphones", true,
                Collections.singletonList(1L), "Headphones", 1, 3);
        assertEquals("TRUSTED_CONNECTED", warnings.get(0).code);
        assertEquals(WarningEngine.Severity.INFO, warnings.get(0).severity);
    }

    @Test
    public void nameChangeRaisesHighWarning() {
        List<WarningEngine.Warning> warnings = WarningEngine.onConnect(
                "AA:BB:CC:DD:EE:FF", "NewName", true,
                Collections.singletonList(1L), "OldName", 1, 3);
        assertTrue(warnings.stream().anyMatch(w -> w.code.equals("IDENTITY_NAME_CHANGED")
                && w.severity == WarningEngine.Severity.HIGH));
    }

    @Test
    public void rapidReconnectRaisesHighWarning() {
        List<WarningEngine.Warning> warnings = WarningEngine.onConnect(
                "AA:BB:CC:DD:EE:FF", "Device", true,
                Arrays.asList(1L, 2L, 3L), "Device", 1, 3);
        assertTrue(warnings.stream().anyMatch(w -> w.code.equals("RAPID_RECONNECT")));
    }

    @Test
    public void multipleConnectionsRaiseMediumWarning() {
        List<WarningEngine.Warning> warnings = WarningEngine.onConnect(
                "AA:BB:CC:DD:EE:FF", "Device", true,
                Collections.singletonList(1L), "Device", 4, 3);
        assertTrue(warnings.stream().anyMatch(w -> w.code.equals("MULTIPLE_CONNECTED")
                && w.severity == WarningEngine.Severity.MEDIUM));
    }

    @Test
    public void untrustedNewBondRaisesHighWarning() {
        List<WarningEngine.Warning> warnings = WarningEngine.onBondChange(
                "AA:BB:CC:DD:EE:FF", "Device", 10, 12, false);
        assertEquals(1, warnings.size());
        assertEquals("NEW_BOND", warnings.get(0).code);
        assertEquals(WarningEngine.Severity.HIGH, warnings.get(0).severity);
    }
}
