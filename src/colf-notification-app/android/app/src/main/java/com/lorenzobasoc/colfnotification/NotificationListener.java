package com.lorenzobasoc.colfnotification;

import android.app.Notification;
import android.content.Context;
import android.content.SharedPreferences;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.util.Log;

public class NotificationListener extends NotificationListenerService {

    private static final String TAG = "NotificationListener";
    private static final String INTESA_PACKAGE = "com.intesasanpaolo.mobile.android"; // Verify this package name
    // Also adding generic for testing/fallback if needed, or widely used Italian bank apps
    // But user specified Intesa San Paolo.
    
    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (!isServiceEnabled()) {
            return;
        }

        String packageName = sbn.getPackageName();
        Log.d(TAG, "Notification received from: " + packageName);

        // Check if it is from Intesa San Paolo
        // Note: Package name might vary slightly (e.g. .android suffix), checking contains for robustness
        if (packageName.toLowerCase().contains("intesasanpaolo")) {
            Notification notification = sbn.getNotification();
            if (notification == null) return;
            
            CharSequence tickerText = notification.tickerText;
            String title = notification.extras.getString(Notification.EXTRA_TITLE);
            String text = notification.extras.getString(Notification.EXTRA_TEXT);
            
            Log.d(TAG, "Intesa Notification: Title=" + title + ", Text=" + text);

            if ((text != null && text.toLowerCase().contains("spesa")) || 
                (title != null && title.toLowerCase().contains("spesa"))) {
                
                Log.i(TAG, "Target notification detected! Triggering actions.");
                
                // 1. Activate VPN
                WireGuardHelper.connect(getApplicationContext());
                
                // 2. Send HTTP Notification
                // Adding a small delay to ensure VPN might be up? 
                // Alternatively, just fire and hope, or retry. Keeping it simple.
                try {
                    Thread.sleep(2000); // 2 seconds delay
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
                
                NetworkHelper.sendNotification(
                    title != null ? title : "Intesa Notification",
                    text != null ? text : "Spesa detected"
                );
            }
        }
    }

    private boolean isServiceEnabled() {
        SharedPreferences prefs = getSharedPreferences("ColfSettings", MODE_PRIVATE);
        return prefs.getBoolean("service_enabled", false);
    }
}
