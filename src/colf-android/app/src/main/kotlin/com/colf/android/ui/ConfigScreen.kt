package com.colf.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.collectAsState
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConfigScreen(viewModel: ConfigViewModel = viewModel()) {
    val settings by viewModel.settings.collectAsState()
    val connectionTestState by viewModel.connectionTestState.collectAsState()
    val context = LocalContext.current

    var bankPackagesText by remember(settings.bankPackages) {
        mutableStateOf(settings.bankPackages.joinToString("\n"))
    }
    var notificationAccessGranted by remember {
        mutableStateOf(NotificationAccessHelper.isNotificationAccessGranted(context))
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("CoLF Notify") }) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text("Configurazione server")

                    OutlinedTextField(
                        value = settings.baseUrl,
                        onValueChange = viewModel::setBaseUrl,
                        label = { Text("Base URL (es. http://10.0.0.2:9902)") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                    )
                    OutlinedTextField(
                        value = settings.token,
                        onValueChange = viewModel::setToken,
                        label = { Text("Token (X-Ingest-Token)") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Button(onClick = { viewModel.testConnection() }) {
                            Text("Testa connessione")
                        }
                        ConnectionTestIndicator(connectionTestState)
                    }
                }
            }

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text("App bancarie da ascoltare (un package per riga)")
                    OutlinedTextField(
                        value = bankPackagesText,
                        onValueChange = {
                            bankPackagesText = it
                            viewModel.setBankPackagesText(it)
                        },
                        label = { Text("es. it.bancaesempio.app") },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                    )
                }
            }

            Card(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("Notifiche bancarie")
                        Text(
                            "Unico interruttore della feature: se è spento, nessuna " +
                                "notifica viene inoltrata a CoLF.",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    Switch(
                        checked = settings.forwardingEnabled,
                        onCheckedChange = viewModel::setForwardingEnabled,
                    )
                }
            }

            HorizontalDivider()

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        if (notificationAccessGranted) {
                            "Accesso alle notifiche: concesso"
                        } else {
                            "Accesso alle notifiche: NON concesso"
                        },
                    )
                    OutlinedButton(onClick = {
                        NotificationAccessHelper.openNotificationAccessSettings(context)
                    }) {
                        Text("Apri impostazioni notifiche")
                    }
                    Button(onClick = {
                        notificationAccessGranted = NotificationAccessHelper.isNotificationAccessGranted(context)
                    }) {
                        Text("Ricontrolla stato permesso")
                    }
                }
            }

        }
    }
}

@Composable
private fun ConnectionTestIndicator(state: ConnectionTestState) {
    when (state) {
        ConnectionTestState.Idle -> Text("")
        ConnectionTestState.Testing -> CircularProgressIndicator(modifier = Modifier.padding(4.dp))
        ConnectionTestState.Ok -> Text("OK, server raggiungibile")
        ConnectionTestState.Unauthorized -> Text("Token errato")
        ConnectionTestState.Unreachable -> Text("Server irraggiungibile")
        ConnectionTestState.InvalidUrl -> Text("URL non valido: correggi il campo Base URL (es. http://10.0.0.2:9902)")
    }
}
