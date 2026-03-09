package com.lorenzobasoc.colfnotification;

import android.content.ComponentName;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.provider.Settings;
import android.text.TextUtils;
import android.widget.Button;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private static final String ENABLED_NOTIFICATION_LISTENERS = "enabled_notification_listeners";
    private Switch toggleButton;
    private TextView statusText;
    private Button permissionButton;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        toggleButton = findViewById(R.id.toggleButton);
        statusText = findViewById(R.id.statusText);
        permissionButton = findViewById(R.id.permissionButton);

        permissionButton.setOnClickListener(v -> {
            startActivity(new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS));
        });

        toggleButton.setOnCheckedChangeListener((buttonView, isChecked) -> {
            saveState(isChecked);
            updateUI(isChecked);
            if (isChecked) {
                WireGuardHelper.connect(this); // Optional: ensure VPN is ready? Or just wait for trigger? 
                // User asked: "se è accesa sta in ascolto".
                // We typically just enable the listener flag.
                // Disconnecting vpn on manual off might be expected?
                // For now, minimal compliance: if listening, we are ready to trigger.
            } else {
                 // Maybe disconnect VPN if we manually turn off app?
                 // The user didn't explicitly say "turn off VPN when app turns off", 
                 // but "bottone per accenderla e spegnerla" implies the whole automation.
                 // We'll leave VPN state alone unless triggered, to avoid accidents.
            }
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        boolean isPermissionGranted = isNotificationServiceEnabled();
        
        if (!isPermissionGranted) {
            statusText.setText(R.string.permission_required);
            permissionButton.setVisibility(Button.VISIBLE);
            toggleButton.setEnabled(false);
        } else {
            permissionButton.setVisibility(Button.GONE);
            toggleButton.setEnabled(true);
            
            boolean isEnabled = loadState();
            toggleButton.setChecked(isEnabled);
            updateUI(isEnabled);
        }
    }

    private void updateUI(boolean isEnabled) {
        if (isEnabled) {
            statusText.setText(R.string.status_listening);
            toggleButton.setText(R.string.service_enabled);
        } else {
            statusText.setText(R.string.status_idle);
            toggleButton.setText(R.string.service_disabled);
        }
    }

    private void saveState(boolean isEnabled) {
        SharedPreferences prefs = getSharedPreferences("ColfSettings", MODE_PRIVATE);
        prefs.edit().putBoolean("service_enabled", isEnabled).apply();
    }

    private boolean loadState() {
        SharedPreferences prefs = getSharedPreferences("ColfSettings", MODE_PRIVATE);
        return prefs.getBoolean("service_enabled", false);
    }

    private boolean isNotificationServiceEnabled() {
        String pkgName = getPackageName();
        final String flat = Settings.Secure.getString(getContentResolver(),
                ENABLED_NOTIFICATION_LISTENERS);
        if (!TextUtils.isEmpty(flat)) {
            final String[] names = flat.split(":");
            for (String name : names) {
                final ComponentName cn = ComponentName.unflattenFromString(name);
                if (cn != null) {
                    if (TextUtils.equals(pkgName, cn.getPackageName())) {
                        return true;
                    }
                }
            }
        }
        return false;
    }
}
